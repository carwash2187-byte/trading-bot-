"""Technical indicators over OHLC series.

Pure Python and dependency-free on purpose, so the test suite runs anywhere
with no install step. Every function takes plain lists and returns a list of
the same length, padded at the front with ``None`` where there is not yet
enough history. Aligning outputs to input length keeps index ``i`` meaning
"bar i" everywhere and removes a whole class of off-by-one bugs.

No trading logic lives here — these are measurements, nothing more.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Optional

from ..brokers.base import Candle

# Spelled with typing.Optional rather than ``float | None``: this is a runtime
# expression, not an annotation, so ``from __future__ import annotations`` does
# not defer it and the newer syntax raises on Python 3.9.
Series = List[Optional[float]]


def _closes(candles: list[Candle]) -> list[float]:
    return [c.close for c in candles]


def sma(values: list[float], period: int) -> Series:
    """Simple moving average."""
    if period <= 0:
        raise ValueError("period must be > 0")
    out: Series = [None] * len(values)
    running = 0.0
    for i, v in enumerate(values):
        running += v
        if i >= period:
            running -= values[i - period]
        if i >= period - 1:
            out[i] = running / period
    return out


def ema(values: list[float], period: int) -> Series:
    """Exponential moving average, seeded with an SMA like most platforms."""
    if period <= 0:
        raise ValueError("period must be > 0")
    out: Series = [None] * len(values)
    if len(values) < period:
        return out
    k = 2.0 / (period + 1.0)
    prev = sum(values[:period]) / period
    out[period - 1] = prev
    for i in range(period, len(values)):
        prev = values[i] * k + prev * (1 - k)
        out[i] = prev
    return out


def rma(values: list[float], period: int) -> Series:
    """Wilder's smoothing — the average RSI and ATR are built on."""
    out: Series = [None] * len(values)
    if len(values) < period:
        return out
    prev = sum(values[:period]) / period
    out[period - 1] = prev
    for i in range(period, len(values)):
        prev = (prev * (period - 1) + values[i]) / period
        out[i] = prev
    return out


def rsi(candles: list[Candle], period: int = 14) -> Series:
    """Relative Strength Index, 0-100."""
    closes = _closes(candles)
    if len(closes) < 2:
        return [None] * len(closes)
    gains = [0.0]
    losses = [0.0]
    for i in range(1, len(closes)):
        change = closes[i] - closes[i - 1]
        gains.append(max(change, 0.0))
        losses.append(max(-change, 0.0))

    avg_gain = rma(gains[1:], period)
    avg_loss = rma(losses[1:], period)

    out: Series = [None] * len(closes)
    for i in range(len(avg_gain)):
        g, l = avg_gain[i], avg_loss[i]
        if g is None or l is None:
            continue
        if l == 0:
            out[i + 1] = 100.0
        else:
            rs = g / l
            out[i + 1] = 100.0 - (100.0 / (1.0 + rs))
    return out


def true_range(candles: list[Candle]) -> list[float]:
    """Per-bar true range."""
    out = []
    for i, c in enumerate(candles):
        if i == 0:
            out.append(c.high - c.low)
        else:
            prev_close = candles[i - 1].close
            out.append(
                max(c.high - c.low, abs(c.high - prev_close), abs(c.low - prev_close))
            )
    return out


def atr(candles: list[Candle], period: int = 14) -> Series:
    """Average True Range — the volatility measure stops are usually sized on."""
    return rma(true_range(candles), period)


@dataclass
class Macd:
    """The three MACD lines, each aligned to the input length."""

    macd: Series
    signal: Series
    histogram: Series


def macd(
    candles: list[Candle],
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> Macd:
    """Moving Average Convergence Divergence.

    The signal line is an EMA *of the MACD line*, so it cannot start until the
    MACD line exists. Running the EMA over the padded series would fold the
    leading ``None`` gap into the seed average, so it is computed over the valid
    slice and shifted back into position.
    """
    closes = _closes(candles)
    fast_line = ema(closes, fast)
    slow_line = ema(closes, slow)

    macd_line: Series = [
        None if f is None or s is None else f - s
        for f, s in zip(fast_line, slow_line)
    ]

    signal_line: Series = [None] * len(closes)
    histogram: Series = [None] * len(closes)
    start = next((i for i, v in enumerate(macd_line) if v is not None), len(macd_line))
    for offset, value in enumerate(ema(macd_line[start:], signal)):
        if value is None:
            continue
        i = start + offset
        signal_line[i] = value
        histogram[i] = macd_line[i] - value
    return Macd(macd=macd_line, signal=signal_line, histogram=histogram)


@dataclass
class Supertrend:
    """The Supertrend line and which way it says the market is going.

    ``direction`` keeps the convention that catches everyone out: **-1 means
    uptrend** and +1 means downtrend, matching TradingView's ``ta.supertrend``.
    Flipping it to something more readable here would make every strategy
    silently disagree with the backtest it was validated against.
    """

    line: Series
    direction: Series

    def flipped_up(self, i: int = -1) -> bool:
        """True if bar ``i`` is the moment the trend turned bullish."""
        return self._flip(i, to=-1.0)

    def flipped_down(self, i: int = -1) -> bool:
        """True if bar ``i`` is the moment the trend turned bearish."""
        return self._flip(i, to=1.0)

    def _flip(self, i: int, to: float) -> bool:
        n = len(self.direction)
        idx = i if i >= 0 else n + i
        if idx <= 0 or idx >= n:
            return False
        now, before = self.direction[idx], self.direction[idx - 1]
        return now == to and before is not None and before != to


def supertrend(
    candles: list[Candle], factor: float = 3.0, period: int = 10
) -> Supertrend:
    """Supertrend — an ATR band that flips sides when price closes through it.

    The bands only ever tighten toward price while a trend holds, and are
    released the moment price closes past them. That ratchet is the whole
    indicator; without it the line would whipsaw on every bar.
    """
    atr_series = atr(candles, period)
    line: Series = [None] * len(candles)
    direction: Series = [None] * len(candles)

    prev_upper = prev_lower = prev_line = None
    prev_dir: int | None = None

    for i, candle in enumerate(candles):
        atr_now = atr_series[i]
        if atr_now is None:
            continue

        hl2 = (candle.high + candle.low) / 2.0
        upper = hl2 + factor * atr_now
        lower = hl2 - factor * atr_now

        if prev_lower is not None and prev_upper is not None:
            prev_close = candles[i - 1].close
            if not (lower > prev_lower or prev_close < prev_lower):
                lower = prev_lower
            if not (upper < prev_upper or prev_close > prev_upper):
                upper = prev_upper

        if prev_dir is None:
            now_dir = 1
        elif prev_line == prev_upper:
            now_dir = -1 if candle.close > upper else 1
        else:
            now_dir = 1 if candle.close < lower else -1

        current = lower if now_dir == -1 else upper
        line[i] = current
        direction[i] = float(now_dir)
        prev_upper, prev_lower, prev_line, prev_dir = upper, lower, current, now_dir

    return Supertrend(line=line, direction=direction)


def vwap(candles: list[Candle], reset_daily: bool = True) -> Series:
    """Volume-weighted average price.

    With ``reset_daily`` the accumulation restarts each calendar day, which is
    how intraday charts draw it.
    """
    out: Series = [None] * len(candles)
    cum_pv = 0.0
    cum_v = 0.0
    current_day = None
    for i, c in enumerate(candles):
        day = c.timestamp.date()
        if reset_daily and day != current_day:
            cum_pv = 0.0
            cum_v = 0.0
            current_day = day
        typical = (c.high + c.low + c.close) / 3.0
        cum_pv += typical * c.volume
        cum_v += c.volume
        out[i] = (cum_pv / cum_v) if cum_v > 0 else None
    return out


@dataclass
class BollingerBands:
    upper: Series
    middle: Series
    lower: Series
    bandwidth: Series


def bollinger(candles: list[Candle], period: int = 20, stdevs: float = 2.0) -> BollingerBands:
    """Bollinger Bands plus bandwidth."""
    closes = _closes(candles)
    mid = sma(closes, period)
    upper: Series = [None] * len(closes)
    lower: Series = [None] * len(closes)
    width: Series = [None] * len(closes)
    for i in range(len(closes)):
        m = mid[i]
        if m is None:
            continue
        window = closes[i - period + 1 : i + 1]
        variance = sum((x - m) ** 2 for x in window) / period
        sd = math.sqrt(variance)
        upper[i] = m + stdevs * sd
        lower[i] = m - stdevs * sd
        width[i] = ((upper[i] - lower[i]) / m) if m else None
    return BollingerBands(upper=upper, middle=mid, lower=lower, bandwidth=width)


def highest(values: list[float], period: int) -> Series:
    """Rolling maximum over ``period`` bars, inclusive of the current bar."""
    out: Series = [None] * len(values)
    for i in range(period - 1, len(values)):
        out[i] = max(values[i - period + 1 : i + 1])
    return out


def lowest(values: list[float], period: int) -> Series:
    """Rolling minimum over ``period`` bars, inclusive of the current bar."""
    out: Series = [None] * len(values)
    for i in range(period - 1, len(values)):
        out[i] = min(values[i - period + 1 : i + 1])
    return out


def kama(
    values: list[float], period: int = 10, fast: int = 2, slow: int = 30
) -> Series:
    """Kaufman Adaptive Moving Average.

    Speeds up when price moves in a straight line and slows down when it
    chops. The ratio driving that is direction travelled divided by distance
    travelled: a trend scores near 1, noise scores near 0.
    """
    out: Series = [None] * len(values)
    if len(values) <= period:
        return out

    fast_sc = 2.0 / (fast + 1.0)
    slow_sc = 2.0 / (slow + 1.0)

    prev = values[period - 1]
    out[period - 1] = prev
    for i in range(period, len(values)):
        direction = abs(values[i] - values[i - period])
        volatility = sum(
            abs(values[j] - values[j - 1]) for j in range(i - period + 1, i + 1)
        )
        # Flat stretch: no information either way, so hold the average still.
        ratio = (direction / volatility) if volatility else 0.0
        smooth = (ratio * (fast_sc - slow_sc) + slow_sc) ** 2
        prev = prev + smooth * (values[i] - prev)
        out[i] = prev
    return out


def williams_r(candles: list[Candle], period: int = 14) -> Series:
    """Williams %R — where price sits in its recent range, from 0 to -100.

    Above -20 is the top of the range, below -80 the bottom.
    """
    out: Series = [None] * len(candles)
    highs = [c.high for c in candles]
    lows = [c.low for c in candles]
    for i in range(period - 1, len(candles)):
        hh = max(highs[i - period + 1 : i + 1])
        ll = min(lows[i - period + 1 : i + 1])
        span = hh - ll
        out[i] = -50.0 if span == 0 else -100.0 * (hh - candles[i].close) / span
    return out


@dataclass
class VolumeNode:
    """One price bucket in a volume profile."""

    price_low: float
    price_high: float
    volume: float

    @property
    def mid(self) -> float:
        return (self.price_low + self.price_high) / 2.0


@dataclass
class VolumeProfile:
    nodes: list[VolumeNode]
    point_of_control: float      # price bucket that traded the most volume
    value_area_low: float
    value_area_high: float


def volume_profile(
    candles: list[Candle], buckets: int = 30, value_area_pct: float = 0.70
) -> VolumeProfile:
    """Distribute volume across price buckets over the given range.

    Each candle's volume is spread evenly across the buckets its high-low range
    touches — a standard approximation when only OHLC is available.
    """
    if not candles:
        raise ValueError("no candles supplied")
    if buckets <= 0:
        raise ValueError("buckets must be > 0")

    lo = min(c.low for c in candles)
    hi = max(c.high for c in candles)
    if hi <= lo:
        hi = lo + 1e-9
    step = (hi - lo) / buckets

    nodes = [VolumeNode(lo + i * step, lo + (i + 1) * step, 0.0) for i in range(buckets)]
    for c in candles:
        first = min(int((c.low - lo) / step), buckets - 1)
        last = min(int((c.high - lo) / step), buckets - 1)
        span = last - first + 1
        share = c.volume / span if span > 0 else c.volume
        for idx in range(first, last + 1):
            nodes[idx].volume += share

    poc_node = max(nodes, key=lambda n: n.volume)
    total = sum(n.volume for n in nodes)

    # Grow outward from the POC until the target share of volume is enclosed.
    target = total * value_area_pct
    poc_idx = nodes.index(poc_node)
    low_idx = high_idx = poc_idx
    covered = poc_node.volume
    while covered < target and (low_idx > 0 or high_idx < buckets - 1):
        below = nodes[low_idx - 1].volume if low_idx > 0 else -1.0
        above = nodes[high_idx + 1].volume if high_idx < buckets - 1 else -1.0
        if above >= below:
            high_idx += 1
            covered += nodes[high_idx].volume
        else:
            low_idx -= 1
            covered += nodes[low_idx].volume

    return VolumeProfile(
        nodes=nodes,
        point_of_control=poc_node.mid,
        value_area_low=nodes[low_idx].price_low,
        value_area_high=nodes[high_idx].price_high,
    )


def compute_all(candles: list[Candle], **params) -> dict[str, object]:
    """Convenience: every indicator at once, keyed by name.

    Handy for handing a fully-annotated history to a strategy without the
    strategy needing to know which functions exist.
    """
    return {
        "rsi": rsi(candles, params.get("rsi_period", 14)),
        "atr": atr(candles, params.get("atr_period", 14)),
        "sma": sma(_closes(candles), params.get("sma_period", 50)),
        "ema": ema(_closes(candles), params.get("ema_period", 200)),
        "vwap": vwap(candles),
        "bollinger": bollinger(
            candles, params.get("bb_period", 20), params.get("bb_stdevs", 2.0)
        ),
    }


def obv(candles: list[Candle]) -> Series:
    """On-balance volume — MambaFX's divergence indicator.

    He reads divergence off OBV, not off MACD:

        "from here to here lower low, look at the obv higher low — that is a huge
        sign of reversal"
        "from here to here lower highs... from here to here higher highs, that is a
        sign of bearish continuation"

    Running total of volume, added on an up close and subtracted on a down close.
    Its level is meaningless; only its shape against price matters.
    """
    out: Series = []
    total = 0.0
    prev: float | None = None
    for c in candles:
        if prev is None:
            out.append(0.0)
        else:
            if c.close > prev:
                total += c.volume
            elif c.close < prev:
                total -= c.volume
            out.append(total)
        prev = c.close
    return out
