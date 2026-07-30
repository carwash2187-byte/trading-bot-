"""MambaFX's three-confirmation setup — Bollinger + RSI + a drawn level.

From the video where he builds the whole thing on screen from a blank chart and
reads out every setting (UQQnN6cry8A). This is the most precisely specified
strategy in his catalogue: he names the indicator periods, the band values, and
the order the confirmations have to arrive in.

His setup, in his words:

    "we're going to click RSI or type in RSI... we're going to go to settings...
    this is where it's important the upper band needs to be 75 and the lower band
    needs to be 25 okay inputs are going to stay 14"

    "anytime the RSI breaks below the 25 Zone we're looking for buys and anytime it
    breaks above the 75 Zone we're looking for sells okay... not always accurate
    do not use it by itself"

    "we're going to type in Bowling your bands okay these settings right here...
    we're going to change the inputs to 34"

Then the three confirmations, in order — and the order matters, because he checks
direction before he will even look at a level:

    1. "first thing that we want to do when we use this strategy is to kind of
       dictate which way the market is moving... this market right here on gbpnzd
       is going down this is a downtrend what does that mean we are only looking
       for sells and nothing else we're not looking for buys"

    2. "our second thing we're going to look for is support or resistance
       obviously we're looking for sells we're on a down position we're looking
       for resistance... we're going to take our box right here and just kind of
       draw this out"

    3. "third confirmation check out our Bower bands they have been broken out of
       indicating a very very weak weak weak Trend that's going to come to an end"

Stop and targets, also his:

    "me personally I want my stop loss Above This Little Resistance okay where
    these Wicks have gone so I'll have my stop loss above that"

    "I'll probably have my take profit maybe one would be like right here just in
    case it stops right here at this little resistance... my takeprofit two will
    then be down in this area"

    "take profit one right there did get smashed okay we would have our stops at
    break even and then boom takeprofit two would have got smashed out"

So the exit is a ladder with a specific sequence: first target pays, the stop then
goes to entry, and the remainder runs to the second target. That sequencing is
what makes his breakeven move safe rather than costly — it happens *after* money
is already banked, not before.

One thing he shows on screen and explicitly does not endorse is a buy/sell robot
indicator: "I usually don't vouch for stuff like this". Not built.
"""

from __future__ import annotations

from datetime import timezone

from ..brokers.base import Candle, OrderSide
from ..data.indicators import bollinger, rsi
from .base import Action, AdjustStop, Enter, Exit, Strategy, StrategyContext


class MambaRsi(Strategy):
    """Downtrend plus resistance plus a broken Bollinger band, then sell.

    Args:
        rsi_period: 14. "inputs are going to stay 14".
        rsi_upper: 75. "the upper band needs to be 75".
        rsi_lower: 25. "the lower band needs to be 25".
        boll_period: 34. "we're going to change the inputs to 34".
        boll_stdevs: 2.0, which is the TradingView default he leaves alone.
        trend_bars: Bars used for "which way is the market moving". He stresses
            this is a rough read, not a precise one -- "we're not looking for the
            actual trend line in a way like this... we just want to see which way
            is the market moving".
        level_bars: Bars searched for the box he draws.
        zone_pct: Half-height of that box, as a fraction of price.
        min_touches: 2. He counts the wicks that reached the level.
        target1: First target, in R. "take profit one".
        target2: Second target, in R. "takeprofit two will then be down in this
            area".
        require_rsi: Whether the RSI band break is mandatory. He says outright
            "do not use it by itself", and he takes the trade on three
            confirmations of which RSI is part of the third -- so it defaults to
            required, matching how he actually places the trade on screen.
        max_trades_per_day: 3.
        max_losses_per_day: 2. "If the second one doesn't work out, we are done
            for the day."
    """

    name = "mamba_rsi"
    timeframe = "15m"
    lookback = 300

    def __init__(
        self,
        rsi_period: int = 14,
        rsi_upper: float = 75.0,
        rsi_lower: float = 25.0,
        boll_period: int = 34,
        boll_stdevs: float = 2.0,
        trend_bars: int = 60,
        level_bars: int = 60,
        zone_pct: float = 0.0006,
        min_touches: int = 2,
        target1: float = 1.5,
        target2: float = 4.0,
        require_rsi: bool = True,
        max_trades_per_day: int = 3,
        max_losses_per_day: int = 2,
    ) -> None:
        self.rsi_period = rsi_period
        self.rsi_upper = rsi_upper
        self.rsi_lower = rsi_lower
        self.boll_period = boll_period
        self.boll_stdevs = boll_stdevs
        self.trend_bars = trend_bars
        self.level_bars = level_bars
        self.zone_pct = zone_pct
        self.min_touches = min_touches
        self.target1 = target1
        self.target2 = target2
        self.require_rsi = require_rsi
        self.max_trades_per_day = max_trades_per_day
        self.max_losses_per_day = max_losses_per_day

    # -- his three confirmations -----------------------------------------

    def _trend(self, candles: list[Candle]) -> int:
        """Confirmation one. A rough read, which is how he describes it."""
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

    def _level(self, candles: list[Candle], want_resistance: bool) -> float | None:
        """Confirmation two: the box he draws, with the wicks that reached it."""
        window = candles[-self.level_bars:]
        if len(window) < 20:
            return None
        zone = window[-1].close * self.zone_pct
        best: float | None = None
        best_touches = 0
        for i in range(3, len(window) - 3):
            bar = window[i]
            if want_resistance:
                if not all(bar.high >= window[j].high
                           for j in range(i - 3, i + 4) if j != i):
                    continue
                level = bar.high
                touches = sum(1 for c in window if abs(c.high - level) <= zone)
            else:
                if not all(bar.low <= window[j].low
                           for j in range(i - 3, i + 4) if j != i):
                    continue
                level = bar.low
                touches = sum(1 for c in window if abs(c.low - level) <= zone)
            if touches < self.min_touches:
                continue
            if touches > best_touches:
                best, best_touches = level, touches
        return best

    def _band_broken(self, candles: list[Candle], direction: int) -> bool:
        """Confirmation three: "our Bower bands they have been broken out of"."""
        bands = bollinger(candles, period=self.boll_period, stdevs=self.boll_stdevs)
        upper = bands.upper[-1] if bands.upper else None
        lower = bands.lower[-1] if bands.lower else None
        if upper is None or lower is None:
            return False
        bar = candles[-1]
        # Selling a weakening push up: price has poked out of the upper band.
        if direction < 0:
            return bar.high >= upper
        return bar.low <= lower

    def _rsi_ok(self, candles: list[Candle], direction: int) -> bool:
        """"anytime the RSI breaks above the 75 Zone we're looking for sells"."""
        if not self.require_rsi:
            return True
        series = rsi(candles, period=self.rsi_period)
        value = series[-1] if series else None
        if value is None:
            return False
        if direction < 0:
            return value >= self.rsi_upper
        return value <= self.rsi_lower

    def _wick_stop(self, candles: list[Candle], level: float, short: bool) -> float:
        """"my stop loss Above This Little Resistance where these Wicks have gone"."""
        window = candles[-self.level_bars:]
        zone = level * self.zone_pct
        if short:
            reached = [c.high for c in window if abs(c.high - level) <= zone * 2]
            return (max(reached) if reached else level) + zone
        reached = [c.low for c in window if abs(c.low - level) <= zone * 2]
        return (min(reached) if reached else level) - zone

    # -- the rules -------------------------------------------------------

    def evaluate(self, context: StrategyContext) -> list[Action]:
        candles = context.candles
        need = max(self.trend_bars, self.level_bars, self.boll_period,
                   self.rsi_period) + 5
        if len(candles) < need:
            return []

        # Position management first, above every entry gate. "take profit one
        # right there did get smashed okay we would have our stops at break even
        # and then boom takeprofit two would have got smashed out" -- so the
        # sequence is bank the first target, THEN move the stop, then run.
        for pos in context.open_positions:
            if pos.comment != self.name or pos.stop_loss is None:
                continue
            risk = abs(pos.entry_price - pos.stop_loss)
            if risk <= 0:
                continue
            price = context.bid if pos.is_long else context.ask
            ahead = ((price - pos.entry_price) if pos.is_long
                     else (pos.entry_price - price))
            if ahead < risk * self.target1:
                continue
            # Whether the first target has already been banked is inferred from
            # the stop: it only sits at or past entry once that has happened, so
            # nothing needs to survive a restart.
            banked = (pos.stop_loss >= pos.entry_price if pos.is_long
                      else pos.stop_loss <= pos.entry_price)
            if not banked:
                half = round(pos.lots / 2, 2)
                if half >= 0.01 and pos.lots > 0.01:
                    return [Exit(ticket=pos.ticket, lots=half, reason="tp1")]
                return [AdjustStop(ticket=pos.ticket, stop_loss=pos.entry_price,
                                   take_profit=pos.take_profit)]
            return [AdjustStop(ticket=pos.ticket, stop_loss=pos.entry_price,
                               take_profit=pos.take_profit)]

        if context.has_position:
            return []
        if context.risk.trades_today(self.name) >= self.max_trades_per_day:
            return []
        if (self.max_losses_per_day > 0
                and context.risk.losses_today(self.name) >= self.max_losses_per_day):
            return []
        if context.news is not None and context.news.active:
            return []

        # One: direction. "we are only looking for sells and nothing else"
        direction = self._trend(candles)
        if direction == 0:
            return []

        # Two: the level, on the side the trade needs.
        level = self._level(candles, want_resistance=direction < 0)
        if level is None:
            return []

        bar = candles[-1]
        zone = bar.close * self.zone_pct
        # Price has to actually be at the level he drew.
        if direction < 0 and bar.high < level - zone:
            return []
        if direction > 0 and bar.low > level + zone:
            return []

        # Three: the band break, plus the RSI he pairs with it.
        if not self._band_broken(candles, direction):
            return []
        if not self._rsi_ok(candles, direction):
            return []

        if direction < 0:
            stop = self._wick_stop(candles, level, short=True)
            if stop <= bar.close:
                return []
            risk = stop - bar.close
            return [Enter(side=OrderSide.SELL, stop_loss=stop,
                          take_profit=bar.close - risk * self.target2,
                          comment=self.name)]

        stop = self._wick_stop(candles, level, short=False)
        if stop >= bar.close:
            return []
        risk = bar.close - stop
        return [Enter(side=OrderSide.BUY, stop_loss=stop,
                      take_profit=bar.close + risk * self.target2,
                      comment=self.name)]
