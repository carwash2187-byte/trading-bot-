"""Real market history, fetched free and cached on disk.

Every backtest in this project so far has run on someone else's server: it
needed a login that expires each session, charged a credit per run, and tested
Pine Script rather than the Python that actually trades. Those were never the
same program, so a good result there was never evidence about *this* bot.

This module removes all three problems. Coinbase's public candle endpoint needs
no key, has 1-hour bars back to 2019, and costs nothing, so a strategy can be
tested a thousand times against the code that will really run it.

Only the exchange's own published candles are used -- no reconstruction from
trades, no gap filling. A missing bar stays missing, because inventing prices is
exactly how a backtest starts lying.
"""

from __future__ import annotations

import csv
import json
import logging
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ..brokers.base import Candle
from .ohlc import resample

log = logging.getLogger("tradebot.history")

API = "https://api.exchange.coinbase.com"

# Coinbase serves at most 300 candles per request and only these granularities.
MAX_CANDLES = 300
GRANULARITIES = {60: "1m", 300: "5m", 900: "15m", 3600: "1h", 21600: "6h", 86400: "1d"}

# The public endpoint allows ~10 requests/second. Deliberately well under it:
# being throttled costs far more time than pacing does.
PACE_SECONDS = 0.25


class HistoryError(RuntimeError):
    """Raised when history cannot be fetched or is unusable."""


def _get(url: str, attempts: int = 4) -> list:
    """GET with backoff. Rate limits and blips are expected, not exceptional."""
    delay = 1.0
    last: Exception | None = None
    for attempt in range(attempts):
        try:
            request = urllib.request.Request(
                url, headers={"User-Agent": "tradebot/1.0"}
            )
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.loads(response.read().decode())
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
            last = exc
            if attempt < attempts - 1:
                time.sleep(delay)
                delay *= 2
    raise HistoryError(f"could not fetch {url}: {last}")


def _rows_to_candles(rows: list) -> list[Candle]:
    """Convert Coinbase's row format, which is not the usual OHLC order.

    Coinbase returns ``[time, low, high, open, close, volume]`` newest-first.
    Reading it as open-high-low-close would silently swap the extremes and make
    every stop test wrong, so the mapping is spelled out rather than zipped.
    """
    out = []
    for row in rows:
        if not isinstance(row, list) or len(row) < 6:
            continue
        stamp, low, high, opened, closed, volume = row[:6]
        out.append(
            Candle(
                timestamp=datetime.fromtimestamp(int(stamp), tz=timezone.utc),
                open=float(opened),
                high=float(high),
                low=float(low),
                close=float(closed),
                volume=float(volume),
            )
        )
    return out


class HistoryCache:
    """Disk-backed store so the same bars are never paid for twice.

    Args:
        directory: where the CSV files live. One file per product/granularity.
    """

    def __init__(self, directory: str | Path = "data/history") -> None:
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)

    def _path(self, product: str, granularity: int) -> Path:
        return self.directory / f"{product.replace('-', '')}_{granularity}.csv"

    def load(self, product: str, granularity: int) -> list[Candle]:
        path = self._path(product, granularity)
        if not path.exists():
            return []
        out = []
        with path.open(newline="") as handle:
            for row in csv.DictReader(handle):
                try:
                    out.append(
                        Candle(
                            timestamp=datetime.fromisoformat(row["timestamp"]),
                            open=float(row["open"]),
                            high=float(row["high"]),
                            low=float(row["low"]),
                            close=float(row["close"]),
                            volume=float(row["volume"]),
                        )
                    )
                except (KeyError, ValueError):
                    continue        # one bad line should not void the cache
        return out

    def save(self, product: str, granularity: int, candles: list[Candle]) -> None:
        path = self._path(product, granularity)
        temporary = path.with_suffix(".tmp")
        with temporary.open("w", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["timestamp", "open", "high", "low", "close", "volume"])
            for c in candles:
                writer.writerow(
                    [c.timestamp.isoformat(), c.open, c.high, c.low, c.close, c.volume]
                )
        temporary.replace(path)     # atomic: a killed run cannot leave a stub


def fetch(
    product: str = "BTC-USD",
    granularity: int = 3600,
    start: datetime | None = None,
    end: datetime | None = None,
    cache: HistoryCache | None = None,
    refresh: bool = False,
) -> list[Candle]:
    """Return candles for a window, fetching only what the cache is missing.

    Args:
        product: Coinbase product id, e.g. ``BTC-USD``.
        granularity: bar size in seconds; must be one Coinbase supports.
        start: window start. Defaults to two years back.
        end: window end. Defaults to now.
        refresh: ignore the cache and refetch the whole window.
    """
    if granularity not in GRANULARITIES:
        raise HistoryError(
            f"granularity {granularity}s unsupported; use one of "
            f"{sorted(GRANULARITIES)}"
        )

    end = end or datetime.now(timezone.utc)
    start = start or (end - timedelta(days=730))
    cache = cache or HistoryCache()

    known = [] if refresh else cache.load(product, granularity)
    have = {c.timestamp for c in known}

    step = timedelta(seconds=granularity * MAX_CANDLES)
    fetched: list[Candle] = []
    cursor = start
    while cursor < end:
        window_end = min(cursor + step, end)
        # Skip a window only if it is already dense. Counting is enough: the
        # exchange itself has gaps, so demanding every slot be filled would
        # refetch the same missing bars forever.
        expected = int((window_end - cursor).total_seconds() // granularity)
        present = sum(1 for t in have if cursor <= t < window_end)
        if expected and present >= expected - 1:
            cursor = window_end
            continue

        url = (
            f"{API}/products/{product}/candles"
            f"?granularity={granularity}"
            f"&start={cursor.isoformat().replace('+00:00', 'Z')}"
            f"&end={window_end.isoformat().replace('+00:00', 'Z')}"
        )
        rows = _get(url)
        if isinstance(rows, dict):
            raise HistoryError(f"{product}: {rows.get('message', rows)}")
        fetched.extend(_rows_to_candles(rows))
        time.sleep(PACE_SECONDS)
        cursor = window_end

    if fetched:
        merged = {c.timestamp: c for c in known}
        merged.update({c.timestamp: c for c in fetched})
        known = sorted(merged.values(), key=lambda c: c.timestamp)
        cache.save(product, granularity, known)
        log.info("%s %ss: +%d bars, %d cached", product, granularity,
                 len(fetched), len(known))

    return [c for c in known if start <= c.timestamp <= end]


def bars(
    product: str = "BTC-USD",
    timeframe: str = "2h",
    start: datetime | None = None,
    end: datetime | None = None,
    cache: HistoryCache | None = None,
) -> list[Candle]:
    """Candles at any timeframe, built up from the nearest one Coinbase serves.

    Coinbase has no 2h or 4h bars, so those are aggregated from 1h. Building
    coarse bars from fine ones is safe; the reverse would require inventing
    the path price took inside the bar.
    """
    source_seconds = _best_source(timeframe)
    source = fetch(product, source_seconds, start, end, cache)
    source_tf = GRANULARITIES[source_seconds]
    if source_tf == timeframe:
        return source
    return resample(source, source_tf, timeframe)


def _best_source(timeframe: str) -> int:
    """Largest native granularity that divides the requested timeframe."""
    from .ohlc import timeframe_minutes

    wanted = timeframe_minutes(timeframe) * 60
    usable = [g for g in sorted(GRANULARITIES, reverse=True) if wanted % g == 0]
    if not usable:
        raise HistoryError(
            f"cannot build {timeframe} bars from Coinbase granularities "
            f"{sorted(GRANULARITIES)}"
        )
    return usable[0]
