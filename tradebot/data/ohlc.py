"""Historical OHLC storage, loading and inspection.

Years of candles across several timeframes, cached on disk as CSV so a
backtest does not re-download every run. No pattern recognition and no trading
logic — this is the shelf the history sits on.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ..brokers.base import Broker, Candle

# Canonical timeframe names -> minutes per bar.
TIMEFRAMES: dict[str, int] = {
    "1m": 1,
    "5m": 5,
    "15m": 15,
    "30m": 30,
    "1h": 60,
    "2h": 120,      # what every strategy in this repo actually runs on
    "4h": 240,
    "6h": 360,      # a native Coinbase granularity, so it must be nameable
    "1d": 1440,
}


def timeframe_minutes(timeframe: str) -> int:
    try:
        return TIMEFRAMES[timeframe.lower()]
    except KeyError:
        raise ValueError(
            f"unknown timeframe {timeframe!r}; expected one of {sorted(TIMEFRAMES)}"
        ) from None


@dataclass(frozen=True)
class Bounds:
    """The time span a series actually covers."""

    start: datetime
    end: datetime
    bars: int

    @property
    def days(self) -> float:
        return (self.end - self.start).total_seconds() / 86_400.0


class CandleStore:
    """Disk-backed OHLC cache, one CSV per symbol and timeframe."""

    def __init__(self, root: str | Path = "data/candles") -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, symbol: str, timeframe: str) -> Path:
        return self.root / f"{symbol.upper()}_{timeframe.lower()}.csv"

    # -- persistence -----------------------------------------------------

    def save(self, symbol: str, timeframe: str, candles: list[Candle]) -> Path:
        """Write a series to disk, sorted and de-duplicated by timestamp."""
        path = self._path(symbol, timeframe)
        merged = self._merge(self.load(symbol, timeframe), candles)
        with path.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.writer(fh)
            writer.writerow(["timestamp", "open", "high", "low", "close", "volume"])
            for c in merged:
                writer.writerow(
                    [c.timestamp.isoformat(), c.open, c.high, c.low, c.close, c.volume]
                )
        return path

    def load(
        self,
        symbol: str,
        timeframe: str,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[Candle]:
        """Read a cached series, optionally trimmed to a window."""
        path = self._path(symbol, timeframe)
        if not path.exists():
            return []
        out: list[Candle] = []
        with path.open("r", encoding="utf-8", newline="") as fh:
            for row in csv.DictReader(fh):
                try:
                    ts = datetime.fromisoformat(row["timestamp"])
                except (KeyError, ValueError):
                    continue  # skip a torn row rather than failing the load
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                if start and ts < start:
                    continue
                if end and ts > end:
                    continue
                out.append(
                    Candle(
                        timestamp=ts,
                        open=float(row["open"]),
                        high=float(row["high"]),
                        low=float(row["low"]),
                        close=float(row["close"]),
                        volume=float(row.get("volume") or 0.0),
                    )
                )
        return out

    @staticmethod
    def _merge(existing: list[Candle], incoming: list[Candle]) -> list[Candle]:
        by_ts = {c.timestamp: c for c in existing}
        by_ts.update({c.timestamp: c for c in incoming})
        return [by_ts[k] for k in sorted(by_ts)]

    # -- acquisition -----------------------------------------------------

    def download(
        self,
        broker: Broker,
        symbol: str,
        timeframe: str,
        years: float = 3.0,
        chunk: int = 5_000,
    ) -> list[Candle]:
        """Pull history back from now, paging backwards through the broker.

        Stops early when the broker stops returning new bars, which is how a
        symbol with a short listing history terminates cleanly.
        """
        minutes = timeframe_minutes(timeframe)
        wanted_bars = int((years * 365 * 24 * 60) / minutes)
        collected: dict[datetime, Candle] = {}
        cursor: datetime | None = None

        while len(collected) < wanted_bars:
            batch = broker.get_candles(symbol, timeframe, chunk, end=cursor)
            if not batch:
                break
            fresh = [c for c in batch if c.timestamp not in collected]
            if not fresh:
                break
            for c in fresh:
                collected[c.timestamp] = c
            cursor = min(c.timestamp for c in batch) - timedelta(minutes=minutes)

        series = [collected[k] for k in sorted(collected)]
        if series:
            self.save(symbol, timeframe, series)
        return series

    def download_all_timeframes(
        self,
        broker: Broker,
        symbol: str,
        timeframes: list[str] | None = None,
        years: float = 3.0,
    ) -> dict[str, list[Candle]]:
        """Fetch several timeframes for one symbol in one call."""
        timeframes = timeframes or ["1m", "5m", "15m", "1h", "1d"]
        return {
            tf: self.download(broker, symbol, tf, years=years) for tf in timeframes
        }

    # -- inspection ------------------------------------------------------

    def bounds(self, symbol: str, timeframe: str) -> Bounds | None:
        rows = self.load(symbol, timeframe)
        if not rows:
            return None
        return Bounds(start=rows[0].timestamp, end=rows[-1].timestamp, bars=len(rows))

    def coverage_report(self, symbol: str) -> dict[str, str]:
        """Human-readable summary of what history is on disk."""
        report = {}
        for tf in TIMEFRAMES:
            b = self.bounds(symbol, tf)
            report[tf] = (
                f"{b.bars} bars, {b.start.date()} to {b.end.date()} ({b.days/365:.1f}y)"
                if b
                else "none"
            )
        return report


def resample(candles: list[Candle], source_tf: str, target_tf: str) -> list[Candle]:
    """Aggregate a fast series into a slower one (1m -> 15m, 1h -> 4h, ...).

    Useful when a broker only serves one granularity but the study needs
    several. Buckets are aligned to the epoch so they line up with what a chart
    would draw.
    """
    src = timeframe_minutes(source_tf)
    dst = timeframe_minutes(target_tf)
    if dst % src != 0:
        raise ValueError(f"{target_tf} is not a whole multiple of {source_tf}")
    if dst == src:
        return list(candles)

    out: list[Candle] = []
    bucket: list[Candle] = []
    bucket_key: int | None = None
    for c in candles:
        key = int(c.timestamp.timestamp() // (dst * 60))
        if bucket_key is None:
            bucket_key = key
        if key != bucket_key:
            out.append(_aggregate(bucket))
            bucket = []
            bucket_key = key
        bucket.append(c)
    if bucket:
        out.append(_aggregate(bucket))
    return out


def _aggregate(bucket: list[Candle]) -> Candle:
    return Candle(
        timestamp=bucket[0].timestamp,
        open=bucket[0].open,
        high=max(c.high for c in bucket),
        low=min(c.low for c in bucket),
        close=bucket[-1].close,
        volume=sum(c.volume for c in bucket),
    )


def to_ascii_chart(candles: list[Candle], width: int = 80, height: int = 20) -> str:
    """Render a quick candlestick-ish chart in the terminal.

    Deliberately dependency-free so history can be eyeballed over SSH. For a
    real chart, hand the same candles to matplotlib or a notebook.
    """
    if not candles:
        return "(no candles)"
    rows = candles[-width:]
    hi = max(c.high for c in rows)
    lo = min(c.low for c in rows)
    span = (hi - lo) or 1e-9

    grid = [[" "] * len(rows) for _ in range(height)]
    for x, c in enumerate(rows):
        def y_of(price: float) -> int:
            return min(height - 1, max(0, int((hi - price) / span * (height - 1))))

        top, bottom = y_of(c.high), y_of(c.low)
        body_top, body_bottom = sorted((y_of(c.open), y_of(c.close)))
        for y in range(top, bottom + 1):
            grid[y][x] = "│"
        for y in range(body_top, body_bottom + 1):
            grid[y][x] = "█" if c.close >= c.open else "▒"

    lines = [f"{hi:>12.5f} ┤" + "".join(grid[0])]
    for y in range(1, height - 1):
        lines.append(" " * 12 + " │" + "".join(grid[y]))
    lines.append(f"{lo:>12.5f} ┤" + "".join(grid[-1]))
    lines.append(
        " " * 14
        + f"{rows[0].timestamp:%Y-%m-%d}".ljust(max(1, len(rows) - 10))
        + f"{rows[-1].timestamp:%Y-%m-%d}"
    )
    return "\n".join(lines)
