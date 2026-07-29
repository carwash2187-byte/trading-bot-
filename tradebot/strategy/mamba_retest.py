"""MambaFX's small-account method: break a level, then trade its retest.

From "$100 Forex Account TRADING STRATEGY | EASY" (I_33XcywuIo), which is the
one video in his catalogue built explicitly for an account this size. Watched
frame by frame; every rule below is something he says or draws, and where it
disagrees with what tested better, his version is what is implemented.

His sequence, in order:

1. "first thing you're gonna do is pretty much turn the higher time frame so
   right here I'm looking at the four hours I'm gonna mark up a zone... price
   has made large rejections to the upside"
2. "price has actually came back retested it with a wick once we saw this wick
   that's when we'd start looking for sales"
3. "we're not gonna look for sales on the for our because you know obviously
   we're using a hundred dollar count we can't really trade the for our because
   you know our stop losses are gonna be too high"
4. "so now what are we gonna do it's going a 15-minute time frame"
5. "price broke below these loaves came back and as you can see retested it" --
   "this is pretty much just like a break and retest strategy"
6. "we get in a short position off that wig"
7. "stop-loss just in the middle or just above this little support zone because
   if it breaks above this support so we don't even want to be into anyways"
8. "I would target this zone... cuz it's the closest and you see a major wick
   rejection"

The distinction that matters most, and the one this file exists for: **the entry
is the retest, not the break.** The existing MambaBreakout enters as the level
gives way. He does not. He lets it break, waits for price to come back to the
level it just broke, and enters when that level rejects price from the other
side. A support that breaks becomes resistance; he sells the retest of it.

That single change is also why this can reach his stated two-to-three trades a
day. A break happens once per level. The retest of a broken level is a second,
separate, later event -- and unlike the break it can be waited for, which means
it can be caught reliably rather than chased.

On reward: he quotes "22 pips stop-loss with a 50 80 take profit" and "16 pips
stop-loss 51 pivot a profit", and the risk/reward boxes drawn on his screen
measure about 17 against 52. So roughly **1:3**, arrived at by targeting the
nearest opposing structure rather than by multiplying the stop. This file
targets structure first and falls back to a multiple only when no structure is
in range, because that is the order he does it in.

On risk he is explicit: "we don't want to risk more than you know three to five
percent max". That is a sizing decision made in run.py, not here, but it is
recorded because it is the number from the man himself.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timezone

from ..brokers.base import Candle, OrderSide
from .base import Action, Enter, Strategy, StrategyContext


@dataclass(frozen=True)
class Level:
    """A price level price has respected, and which side it was broken from."""

    price: float
    touches: int
    broken_down: bool  # True: was support, broke downward, now resistance


class MambaRetest(Strategy):
    """Break and retest, the way he teaches it for a small account.

    Args:
        higher_tf_bars: Bars making up the "four hour" view whose rejection sets
            the direction. 96 fifteen-minute bars is 24 hours.
        level_lookback: How far back to hunt for the level that gets broken.
        zone_pct: Half-height of a level's zone, as a fraction of price. He draws
            levels as boxes, not lines -- "stop-loss just in the middle or just
            above this little support zone" only means something if the level has
            height.
        min_touches: Touches needed before he trusts a level. He counts wicks
            aloud on the chart before drawing anything.
        retest_bars: How long after a break the retest still counts. A level
            revisited weeks later is not the same trade.
        stop_zone_frac: Where in the zone the stop sits, as a fraction of zone
            height beyond the far edge. His words allow either the middle or just
            past it; this puts it just past, which is the version he draws.
        fallback_reward: Reward multiple used only when no opposing structure is
            within range. His drawn trades come out near 1:3.
        max_trades_per_day: "two, three when I like it."
    """

    name = "mamba_retest"
    timeframe = "15m"
    lookback = 500

    def __init__(
        self,
        higher_tf_bars: int = 96,
        level_lookback: int = 200,
        zone_pct: float = 0.0004,
        min_touches: int = 2,
        retest_bars: int = 24,
        stop_zone_frac: float = 0.5,
        fallback_reward: float = 3.0,
        max_trades_per_day: int = 3,
    ) -> None:
        self.higher_tf_bars = higher_tf_bars
        self.level_lookback = level_lookback
        self.zone_pct = zone_pct
        self.min_touches = min_touches
        self.retest_bars = retest_bars
        self.stop_zone_frac = stop_zone_frac
        self.fallback_reward = fallback_reward
        self.max_trades_per_day = max_trades_per_day

    # -- reading the chart the way he reads it ---------------------------

    def _higher_tf_bias(self, candles: list[Candle]) -> int:
        """-1 down, +1 up, 0 no opinion.

        "price has made large rejections to the upside... we already know that on
        the four-hour we should be dropping so now we can go on the smaller
        charts and look for beautiful entries." The rejection he points at is
        price reaching the top of its higher-timeframe range and failing there,
        so bias is read from where price sits in that range.
        """
        if len(candles) < self.higher_tf_bars:
            return 0
        htf = candles[-self.higher_tf_bars:]
        high = max(c.high for c in htf)
        low = min(c.low for c in htf)
        if high <= low:
            return 0
        pos = (candles[-1].close - low) / (high - low)
        if pos > 0.66:
            return -1  # up at resistance, he looks for sells
        if pos < 0.34:
            return 1
        return 0

    def _broken_levels(self, candles: list[Candle]) -> list[Level]:
        """Levels that were respected, then broken, recently enough to retest."""
        window = candles[-self.level_lookback:]
        if len(window) < 40:
            return []

        price = window[-1].close
        zone = price * self.zone_pct
        out: list[Level] = []

        # Walk candidate swing levels. A swing low that later gets closed
        # through is a support that became resistance -- his sell setup.
        for i in range(10, len(window) - self.retest_bars - 1):
            bar = window[i]

            is_swing_low = all(
                bar.low <= window[j].low for j in range(i - 5, i + 6) if j != i
            )
            is_swing_high = all(
                bar.high >= window[j].high for j in range(i - 5, i + 6) if j != i
            )
            if not (is_swing_low or is_swing_high):
                continue

            level = bar.low if is_swing_low else bar.high
            touches = sum(
                1 for c in window[max(0, i - 20):i + 20]
                if abs((c.low if is_swing_low else c.high) - level) <= zone
            )
            if touches < self.min_touches:
                continue

            # Did price later close clean through it, and how long ago?
            after = window[i + 1:]
            broke_at = None
            for k, c in enumerate(after):
                if is_swing_low and c.close < level - zone:
                    broke_at = k
                    break
                if is_swing_high and c.close > level + zone:
                    broke_at = k
                    break
            if broke_at is None:
                continue
            # Still inside the retest window? A level broken long ago is stale.
            if len(after) - broke_at > self.retest_bars:
                continue

            out.append(Level(price=level, touches=touches, broken_down=is_swing_low))

        return out

    def _nearest_target(
        self, candles: list[Candle], entry: float, short: bool
    ) -> float | None:
        """The closest opposing structure, which is what he actually targets.

        "I would target this zone right or this sound but I would stick from now
        to this zone cuz it's the closest and you see a major wick rejection."
        """
        window = candles[-self.level_lookback:]
        zone = entry * self.zone_pct
        best: float | None = None
        for i in range(5, len(window) - 5):
            bar = window[i]
            if short:
                if not all(bar.low <= window[j].low for j in range(i - 5, i + 6) if j != i):
                    continue
                if bar.low >= entry - zone * 4:
                    continue  # must be meaningfully below us
                if best is None or bar.low > best:
                    best = bar.low  # closest below
            else:
                if not all(bar.high >= window[j].high for j in range(i - 5, i + 6) if j != i):
                    continue
                if bar.high <= entry + zone * 4:
                    continue
                if best is None or bar.high < best:
                    best = bar.high
        return best

    def _trades_today(self, context: StrategyContext) -> int:
        today = context.now.astimezone(timezone.utc).date()
        return sum(
            1 for p in context.open_positions
            if p.comment == self.name and p.opened_at.date() == today
        )

    # -- the rules -------------------------------------------------------

    def evaluate(self, context: StrategyContext) -> list[Action]:
        candles = context.candles
        if len(candles) < self.higher_tf_bars + 20:
            return []
        if context.has_position:
            return []
        if self._trades_today(context) >= self.max_trades_per_day:
            return []
        if context.news is not None and context.news.active:
            return []

        bias = self._higher_tf_bias(candles)
        if bias == 0:
            return []

        bar = candles[-1]
        zone = bar.close * self.zone_pct
        stop_room = zone * (1.0 + self.stop_zone_frac)

        for level in self._broken_levels(candles):
            # A support broken downward is now resistance: sell its retest.
            # Only if the higher timeframe agrees, which is his whole point.
            if level.broken_down and bias < 0:
                # "we get in a short position off that wig" -- the bar must
                # REACH back up into the zone and close back below it. A close
                # above means the level did not hold and there is no trade.
                if not (bar.high >= level.price - zone and bar.close < level.price):
                    continue
                stop = level.price + stop_room
                risk = stop - bar.close
                if risk <= 0:
                    continue
                target = self._nearest_target(candles, bar.close, short=True)
                if target is None or target >= bar.close - risk:
                    target = bar.close - risk * self.fallback_reward
                return [Enter(
                    side=OrderSide.SELL,
                    stop_loss=stop,
                    take_profit=target,
                    comment=self.name,
                )]

            # A resistance broken upward is now support: buy its retest.
            if (not level.broken_down) and bias > 0:
                if not (bar.low <= level.price + zone and bar.close > level.price):
                    continue
                stop = level.price - stop_room
                risk = bar.close - stop
                if risk <= 0:
                    continue
                target = self._nearest_target(candles, bar.close, short=False)
                if target is None or target <= bar.close + risk:
                    target = bar.close + risk * self.fallback_reward
                return [Enter(
                    side=OrderSide.BUY,
                    stop_loss=stop,
                    take_profit=target,
                    comment=self.name,
                )]

        return []
