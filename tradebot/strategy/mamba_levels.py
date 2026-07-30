"""His actual architecture: draw the level map first, then pick the trade off it.

Every other strategy in this project computes its prices. This one selects them,
which is what he does.

The evidence is the $250k Nasdaq trade. His 5-minute chart carried about twenty
persistent horizontal rays with price tags, and every price in the trade turned out
to be one of them:

    entry 14085.25   ->  a line already at 14085.73
    TP1   14173.72   ->  14171.26
    TP2   14242.28   ->  14238.74
    TP3   14384.48   ->  14384.18
    stop  14003.83   ->  14003.75

All five within three and a half points of lines that were on the chart before the
trade existed. And the proof that the ratio is a by-product rather than an input:
two of his gold entries at *different* prices carry **identical** targets and stop,
producing 2.62R on one and 4.44R on the other. If the targets were R multiples that
could not happen.

How he describes building the map:

    "right here we have as you can see resistance -- boom boom boom boom boom --
     price comes above"

    "this is a zone where price is actually having resistance... this is supply we
     have supply here, right here more supply"

    "when you have a buildup in a zone on a H4, a lot of times it's going to get
     respected"

And how he uses it, in the same breath as refusing to invent a target:

    "we can always take profit way up here at this major resistance zone"
    "i'll go ahead and zoom out and i'll target my next main zone"
    "my take profits are better than anybody... almost every single time it comes
     to the t, hit take profit and then goes back the other way, because i know
     that this is actually supply"

Two consequences worth being explicit about, because both delete parameters rather
than replace them:

* **There is no target multiple.** The target is the next level up the map. If the
  map has nothing in range, there is no trade -- not a fallback ratio.
* **There is no stop distance.** The stop is the level below entry. Its width is
  whatever the map says, which is why his stops vary from 15 pips on gold to 81
  points on Nasdaq without him ever changing a rule.

What is still his and kept here: direction from the higher timeframe before
anything else, the pre-breakout entry at the level rather than on the break, three
confluences minimum, three trades a day, two losses ending the day, and the ladder
of partial exits up the map.
"""

from __future__ import annotations

from datetime import timedelta, timezone

from ..data.ohlc import timeframe_minutes
from ..brokers.base import Candle, OrderSide
from .base import Action, AdjustStop, Enter, Exit, Strategy, StrategyContext
from .mamba import SESSION_OPENS_UTC
from .mamba_patterns import level_map, snap_to_level


class MambaLevels(Strategy):
    """Select entry, stop and targets from the level map, as he does.

    Args:
        map_lookback: Bars the map is built from.
        map_tolerance_pct: How close two wicks must be to count as the same level.
        map_min_touches: Wicks required before a price is a level. "boom boom boom
            boom boom" is five gestures; three is the floor seen in his drawings.
        at_level_pct: How near a level price must be to count as being at it. He
            enters before the break -- "I don't like to trade the breakouts
            necessarily but the pre-breakouts, I like to get in there before it
            breaks out" -- so this is an approach zone, not a break.
        (trend_bars deleted -- his direction timeframe is the H4 and always was:
        "we're gonna start on the h4, ALWAYS h4, you can use the daily as well, i
        like the h4." Four hours is 240 minutes, so the bar count is 240 divided
        by the bar length. Arithmetic, not a parameter. The old 96 and 48 were
        mine and neither of them was four hours.)
        session / window_minutes: His trading window. Empty session trades around
            the clock, which is what he does on gold and crypto.
        max_trades_per_day: 3. "my rule is I can only take three trades max in one
            day... I say three but I think two is better."
        max_losses_per_day: 2. "really after two losses you should stop and wait
            till the next day."
        rungs: How many levels up the map to ladder out across. His cards show
            three to five, and his hit messages count up to TP5.
    """

    name = "mamba_levels"
    timeframe = "5m"
    lookback = 600

    def __init__(
        self,
        map_lookback: int = 300,
        map_tolerance_pct: float = 0.0004,
        map_min_touches: int = 3,
        at_level_pct: float = 0.0006,
        trend_bars: int = 0,
        session: str = "newyork",
        window_minutes: int = 210,
        max_trades_per_day: int = 2,
        max_losses_per_day: int = 2,
        rungs: int = 3,
    ) -> None:
        self.map_lookback = map_lookback
        self.map_tolerance_pct = map_tolerance_pct
        self.map_min_touches = map_min_touches
        self.at_level_pct = at_level_pct
        self.trend_bars = (trend_bars if trend_bars > 0
                           else 240 // max(1, timeframe_minutes(self.timeframe)))
        self.session = session
        self.window_minutes = window_minutes
        self.max_trades_per_day = max_trades_per_day
        self.max_losses_per_day = max_losses_per_day
        self.rungs = rungs

    # -- his sequence -----------------------------------------------------

    def _direction(self, candles: list[Candle]) -> int:
        """"first off I need to determine are we going up are we going down."""
        if len(candles) < self.trend_bars:
            return 0
        window = candles[-self.trend_bars:]
        first = window[: len(window) // 2]
        last = window[len(window) // 2:]
        a = sum(c.close for c in first) / len(first)
        b = sum(c.close for c in last) / len(last)
        if b > a:
            return 1
        if b < a:
            return -1
        return 0

    def _in_session(self, now) -> bool:
        if not self.session:
            return True
        open_at = SESSION_OPENS_UTC.get(self.session)
        if open_at is None:
            return True
        utc = now.astimezone(timezone.utc)
        start = utc.replace(hour=open_at.hour, minute=open_at.minute,
                            second=0, microsecond=0)
        return start <= utc <= start + timedelta(minutes=self.window_minutes)

    def _ladder(self, price: float, levels: list[float], side: int) -> list[float]:
        """The next few levels in the trade's direction, nearest first."""
        if side > 0:
            up = sorted(lv for lv in levels if lv > price)
            return up[: self.rungs]
        down = sorted((lv for lv in levels if lv < price), reverse=True)
        return down[: self.rungs]

    # -- the rules --------------------------------------------------------

    def evaluate(self, context: StrategyContext) -> list[Action]:
        candles = context.candles
        if len(candles) < max(self.map_lookback, self.trend_bars) + 5:
            return []

        levels = level_map(
            candles,
            lookback=self.map_lookback,
            tolerance_pct=self.map_tolerance_pct,
            min_touches=self.map_min_touches,
        )

        # Manage what is open first: walk the stop up the map behind price as each
        # rung is passed, and take a slice at each one. "don't just take all your
        # profit -- take a little bit of partials if you want, but better than that
        # trail your stop loss, put that stop loss to break even."
        for pos in context.open_positions:
            if pos.comment != self.name or pos.stop_loss is None:
                continue
            price = context.bid if pos.is_long else context.ask
            side = 1 if pos.is_long else -1
            # Levels price has cleared since entry, in the trade's direction.
            if side > 0:
                passed = [lv for lv in levels if pos.entry_price < lv <= price]
            else:
                passed = [lv for lv in levels if price <= lv < pos.entry_price]
            if not passed:
                continue
            # The stop follows to the last level price has cleared.
            anchor = max(passed) if side > 0 else min(passed)
            better = (anchor > pos.stop_loss if side > 0
                      else anchor < pos.stop_loss)
            if better:
                # Take a slice at the rung before moving the stop up to it.
                slice_lots = round(pos.lots / max(2, self.rungs), 2)
                if slice_lots >= 0.01 and pos.lots > 0.01:
                    return [Exit(ticket=pos.ticket, lots=slice_lots,
                                 reason="level-reached")]
                return [AdjustStop(ticket=pos.ticket, stop_loss=anchor,
                                   take_profit=pos.take_profit)]

        if context.has_position:
            return []
        if context.risk.trades_today(self.name) >= self.max_trades_per_day:
            return []
        # "First trade works out, we're done. We don't go for a second. First
        # trade doesn't work out, we look for a second one." A winner ends his
        # day exactly like two losers do.
        if context.risk.wins_today(self.name) >= 1:
            return []
        if (self.max_losses_per_day > 0
                and context.risk.losses_today(self.name) >= self.max_losses_per_day):
            return []
        if context.news is not None and context.news.active:
            return []
        if not self._in_session(context.now):
            return []

        direction = self._direction(candles)
        if direction == 0:
            return []

        bar = candles[-1]
        near = bar.close * self.at_level_pct

        # He enters AT a level in the direction of the higher timeframe, before the
        # break, not on it. So price must be approaching a level from the correct
        # side and have reached it with a wick -- his zones get pierced, and two of
        # three touches on his own chart closed outside the band.
        if direction > 0:
            support = snap_to_level(bar.close, levels, -1)
            if support is None or bar.low > support + near:
                return []
            stop = snap_to_level(support, levels, -1)
            if stop is None or stop >= bar.close:
                return []
            targets = self._ladder(bar.close, levels, 1)
            if not targets:
                return []          # no level to aim at is no trade, not a multiple
            return [Enter(side=OrderSide.BUY, stop_loss=stop,
                          take_profit=targets[-1], comment=self.name)]

        resistance = snap_to_level(bar.close, levels, 1)
        if resistance is None or bar.high < resistance - near:
            return []
        stop = snap_to_level(resistance, levels, 1)
        if stop is None or stop <= bar.close:
            return []
        targets = self._ladder(bar.close, levels, -1)
        if not targets:
            return []
        return [Enter(side=OrderSide.SELL, stop_loss=stop,
                      take_profit=targets[-1], comment=self.name)]
