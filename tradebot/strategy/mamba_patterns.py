"""The chart patterns MambaFX names, as reusable detectors.

Four things he refers to constantly and none of which existed in the code. Each
one here is built from what he says about it, and nothing else.

**Double top and bottom** — he reads them as the letter M and W:

    "whenever the market makes an m uh it's pretty obvious what's going to happen
    right we have a double top resistance while the beginning of the letter m has
    been created"

    "on the h4 you want to find either a major support or major resistance that
    price has showed it's going to respect for example right what do we have here
    beautiful beautiful double bottom strong support made"

And he pairs it straight into the Fibonacci gold zone, which is why both live in
this project rather than one replacing the other:

    "I know a lot of you guys are asking you see a double top like why is this your
    entry check this out you're gonna take... my Fibonacci I'm gonna draw from this
    low to this high what do we have look at this beautiful 50 and a 6-1-8
    rejection"

**Engulfing candle** — his test is size relative to what came before, not the
textbook two-candle definition:

    "i have my build up zone right after the build up zone we had a beautiful
    beautiful bearish engulfing candle yes we had a little bit of a rejection but
    overall this is pretty much engulfing every candle from the last it's been a
    cool minute since it's been that big"

    "why do I still believe this is a bullish trade because look at the size of
    this candle this is a very large engulfing bullish candle"

    "we saw this candle here closed not only a ginormous bullish engulfing candle
    but it closed above the tops of those rejections"

So: engulfs the previous candle's range, AND is large against the recent average,
AND closes beyond the level being tested. All three, because he says all three.

**Fair value gap** — a gap left behind by a fast move, which price returns to:

    "Right here, we're going to have a fair value gap."
    "We have that other fair value gap now supporting price."
    "Hopefully, maybe go to break even once we get down into this order block here,
    just in case price does react off of it."

**Liquidity sweep** — price pushes past an old extreme and immediately fails back:

    "I'm liking this liquidity that we're building up up here."
    "if you guys remember, our entry came from this 4-hour liquidity sweep."
    "the next point could be here as an area of liquidity."

**MACD divergence** — stated once, precisely:

    "lower lows higher high on our macd all that means is that price is bound to
    reverse"

Price making a lower low while MACD makes a higher low is the classic reading of
that sentence, and it is what is built.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..brokers.base import Candle
from ..data.indicators import ema


@dataclass(frozen=True)
class DoublePattern:
    """An M or a W: two extremes at a similar price with a pullback between."""

    level: float        # the shared high (M) or low (W)
    is_top: bool        # True for M, False for W
    neckline: float     # the pullback between the two peaks


def double_top_bottom(
    candles: list[Candle],
    lookback: int = 60,
    tolerance_pct: float = 0.0004,
    min_separation: int = 6,
    fresh_bars: int = 5,
) -> DoublePattern | None:
    """"the beginning of the letter m has been created" / "double bottom".

    Two peaks within ``tolerance_pct`` of each other, at least ``min_separation``
    bars apart, with a meaningful pullback between them. He does not require them
    to be exact -- "resistance and support lines do not need to be perfect".
    """
    window = candles[-lookback:]
    if len(window) < min_separation * 3:
        return None
    tol = window[-1].close * tolerance_pct

    def swings(highs: bool) -> list[tuple[int, float]]:
        out = []
        for i in range(2, len(window) - 2):
            bar = window[i]
            if highs:
                if all(bar.high >= window[j].high
                       for j in range(i - 2, i + 3) if j != i):
                    out.append((i, bar.high))
            else:
                if all(bar.low <= window[j].low
                       for j in range(i - 2, i + 3) if j != i):
                    out.append((i, bar.low))
        return out

    for highs in (True, False):
        peaks = swings(highs)
        # Walk the most recent pairs first: the freshest M or W is the live one.
        for a in range(len(peaks) - 1, 0, -1):
            for b in range(a - 1, -1, -1):
                i2, v2 = peaks[a]
                i1, v1 = peaks[b]
                # The pattern has to have JUST formed. Searching every historical
                # pair in the window found a match on 78% of bars, which is the
                # same as having no detector -- a double top he would point at is
                # one whose second peak is the thing price is doing right now.
                if len(window) - 1 - i2 > fresh_bars:
                    continue
                if i2 - i1 < min_separation:
                    continue
                if abs(v2 - v1) > tol:
                    continue
                between = window[i1:i2 + 1]
                if not between:
                    continue
                neck = (min(c.low for c in between) if highs
                        else max(c.high for c in between))
                # The dip between the peaks has to be several times the
                # tolerance, or two ordinary swings in a drift count as an M.
                if abs(v1 - neck) < tol * 5:
                    continue
                return DoublePattern(level=(v1 + v2) / 2.0, is_top=highs,
                                     neckline=neck)
    return None


def engulfing(
    candles: list[Candle],
    size_mult: float = 1.6,
    average_bars: int = 20,
    beyond: float | None = None,
) -> int:
    """His engulfing candle. Returns +1 bullish, -1 bearish, 0 neither.

    Three conditions, because he names three: it swallows the previous candle's
    range, it is large against the recent average ("it's been a cool minute since
    it's been that big"), and if a level is supplied it must close beyond it
    ("closed above the tops of those rejections").
    """
    if len(candles) < average_bars + 2:
        return 0
    bar = candles[-1]
    prev = candles[-2]
    body = abs(bar.close - bar.open)
    if body <= 0:
        return 0

    recent = candles[-average_bars - 1:-1]
    avg = sum(abs(c.close - c.open) for c in recent) / len(recent)
    if avg <= 0 or body < avg * size_mult:
        return 0

    swallows = bar.high >= prev.high and bar.low <= prev.low
    if not swallows:
        return 0

    if bar.close > bar.open:
        if beyond is not None and bar.close <= beyond:
            return 0
        return 1
    if beyond is not None and bar.close >= beyond:
        return 0
    return -1


def fair_value_gap(
    candles: list[Candle], lookback: int = 40, min_gap_pct: float = 0.0004
) -> tuple[float, float] | None:
    """A gap left by a fast move that price has not yet filled.

    "Right here, we're going to have a fair value gap." / "We have that other fair
    value gap now supporting price."

    Three consecutive bars where the middle one runs so hard that bar 1 and bar 3
    do not overlap. The untouched space between them is the gap.
    """
    window = candles[-lookback:]
    if len(window) < 4:
        return None
    price = window[-1].close
    for i in range(len(window) - 3, 0, -1):
        a, c = window[i - 1], window[i + 1]
        # Gap up: the third bar's low sits above the first bar's high.
        if c.low > a.high and (c.low - a.high) / price >= min_gap_pct:
            gap = (a.high, c.low)
            # Only interesting while still unfilled.
            if all(bar.low > gap[0] for bar in window[i + 2:]):
                return gap
        if a.low > c.high and (a.low - c.high) / price >= min_gap_pct:
            gap = (c.high, a.low)
            if all(bar.high < gap[1] for bar in window[i + 2:]):
                return gap
    return None


def liquidity_sweep(
    candles: list[Candle], lookback: int = 40, bars_back: int = 3
) -> int:
    """"our entry came from this 4-hour liquidity sweep". +1 up, -1 down, 0 none.

    Price pushes through an old extreme and closes straight back inside it. The
    stops beyond that extreme get taken and the move fails -- which is why he
    treats the failure as the signal rather than the break.
    """
    window = candles[-lookback:]
    if len(window) < bars_back + 5:
        return 0
    recent = window[-bars_back:]
    older = window[:-bars_back]
    old_high = max(c.high for c in older)
    old_low = min(c.low for c in older)
    bar = window[-1]

    # Swept the highs and closed back below: the sweep points down.
    if any(c.high > old_high for c in recent) and bar.close < old_high:
        return -1
    if any(c.low < old_low for c in recent) and bar.close > old_low:
        return 1
    return 0


def macd_divergence(
    candles: list[Candle], fast: int = 12, slow: int = 26, lookback: int = 40
) -> int:
    """"lower lows higher high on our macd... price is bound to reverse".

    Returns +1 when price makes a lower low but MACD does not (bullish
    divergence), -1 when price makes a higher high but MACD does not.
    """
    if len(candles) < slow + lookback:
        return 0
    closes = [c.close for c in candles]
    ef = ema(closes, fast)
    es = ema(closes, slow)
    line = [
        (a - b) if (a is not None and b is not None) else None
        for a, b in zip(ef, es)
    ]
    window = candles[-lookback:]
    macd = line[-lookback:]
    if any(v is None for v in macd):
        return 0

    half = lookback // 2
    p_first, p_last = window[:half], window[half:]
    m_first, m_last = macd[:half], macd[half:]

    # Price lower low, MACD higher low -> bullish divergence.
    if (min(c.low for c in p_last) < min(c.low for c in p_first)
            and min(m_last) > min(m_first)):
        return 1
    if (max(c.high for c in p_last) > max(c.high for c in p_first)
            and max(m_last) < max(m_first)):
        return -1
    return 0
