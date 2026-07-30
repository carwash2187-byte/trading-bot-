"""MambaFX's "gold zone" — the Fibonacci retracement he actually trades.

Fibonacci turned up in 14 of his videos and 36 separate statements, which makes it
his most-used tool. He is unusually precise about it, and unusually restrictive:
out of the whole Fibonacci toolkit he trades **two levels only**.

    "we wait for it to come back and reject our gold zone which is the zero five
    zone or the 0.61 our 0.618 zone"

    "the Fibonacci is just a zero point five or six one eight zone that's the only
    zones I want to see get rejected"

    "price does not break through this gold Zone that 0.5 68618 rejection Zone
    then I'm fine"

    "look at this beautiful 50 and a 6-1-8 rejection beautiful rejection right
    here"

So the zone is **0.5 to 0.618 of the move**, he calls it the gold zone, and price
being rejected there is the trade. He mentions 0.382 once as an alternative
("it could be a 382 or a 50 rejection") but every other reference is 0.5-0.618.

How he draws it, which matters as much as the levels:

    "take my Fibonacci I'm gonna draw from this low to this high"

    "I'm not gonna draw my Fibonacci from this wick because this candlestick to me
    is not really set as that push"

    "I'm gonna go and draw my Fibonacci from this wick right here to the top"

He draws it across one push -- the impulse move -- from the wick that genuinely
started it to the extreme that ended it. His refusal to use a wick that is "not
really set as that push" is why this file requires the move to be a real one:
large relative to the noise around it, not just any two adjacent swings.

Then the entry is the retracement being refused:

    "what am I gonna do here I'm gonna wait for a Fibonacci setup to occur now
    that I see this huge rejection to the downside"

    "very simple we wait for it to come back and reject our gold zone"

    "you go on the 15 and get your Fibonacci entry"

And he stacks it with everything else rather than trading it alone:

    "that's two confirmations if not like six by because we already know the h4
    shown bullish the MA is our crossing over on the h4 the [MAs] have crossed
    over on the 15 we've got our fibonacci zone on this choppy setup and now we
    see a support on a former resistance this is a great buy"

    "instead of just looking for five minute 15 minute entries just randomly using
    your fibonacci look at higher time frames and see what's going on"

The moving-average crossover in that list is built here as an option, because he
names it as one of his confirmations in the same breath as the gold zone.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timezone

from ..brokers.base import Candle, OrderSide
from ..data.indicators import ema
from .mamba_patterns import double_top_bottom, macd_divergence
from .base import Action, Enter, Strategy, StrategyContext


@dataclass(frozen=True)
class Push:
    """One impulse move, and the gold zone measured across it."""

    low: float
    high: float
    up: bool          # True: the push went up, so the retracement comes down
    zone_near: float  # the 0.5 level
    zone_far: float   # the 0.618 level


class MambaFib(Strategy):
    """Trade the rejection of his 0.5-0.618 gold zone.

    Args:
        push_bars: Bars searched for the impulse move to measure across.
        min_push_pct: How large the move must be, as a fraction of price, before
            it counts as a push at all. This is the code for "this candlestick to
            me is not really set as that push".
        fib_near: 0.5. "the zero five zone".
        fib_far: 0.618. "the 0.61 our 0.618 zone".
        ma_fast, ma_slow: The crossover he lists among his confirmations. Zero
            disables.
        higher_tf_bars: The H4 view he checks first. "we already know the h4 shown
            bullish".
        reward: 3.0, his usual. The stop is the far end of the push, so reward is
            taken as a multiple rather than from structure.
        stop_beyond_pct: How far past the push extreme the stop sits.
        max_trades_per_day: 3.
        max_losses_per_day: 2. "we are done for the day and we come back tomorrow".
    """

    name = "mamba_fib"
    timeframe = "15m"
    lookback = 400

    def __init__(
        self,
        push_bars: int = 60,
        min_push_pct: float = 0.004,
        fib_near: float = 0.5,
        fib_far: float = 0.618,
        ma_fast: int = 9,
        ma_slow: int = 21,
        higher_tf_bars: int = 96,
        reward: float = 3.0,
        stop_beyond_pct: float = 0.0008,
        max_trades_per_day: int = 3,
        max_losses_per_day: int = 2,
        require_double: bool = False,
        require_macd_divergence: bool = False,
    ) -> None:
        self.push_bars = push_bars
        self.min_push_pct = min_push_pct
        self.fib_near = fib_near
        self.fib_far = fib_far
        self.ma_fast = ma_fast
        self.ma_slow = ma_slow
        self.higher_tf_bars = higher_tf_bars
        self.reward = reward
        self.stop_beyond_pct = stop_beyond_pct
        self.max_trades_per_day = max_trades_per_day
        self.max_losses_per_day = max_losses_per_day
        # He pairs the two explicitly, in one sentence: "you see a double top
        # like why is this your entry check this out you're gonna take... my
        # Fibonacci I'm gonna draw from this low to this high... look at this
        # beautiful 50 and a 6-1-8 rejection". So the M is what makes the gold
        # zone worth trading.
        self.require_double = require_double
        # "lower lows higher high on our macd all that means is that price is
        # bound to reverse" -- a reversal warning, so it must point the same way
        # as the trade.
        self.require_macd_divergence = require_macd_divergence

    # -- drawing it the way he draws it ----------------------------------

    def _push(self, candles: list[Candle]) -> Push | None:
        """The impulse move to measure across: "from this low to this high".

        Finds the largest clean one-directional move in the window. Requires it to
        be big enough to be a real push, because he explicitly refuses to draw
        from a candle that is "not really set as that push".
        """
        window = candles[-self.push_bars:]
        if len(window) < 15:
            return None

        lows = [(i, c.low) for i, c in enumerate(window)]
        highs = [(i, c.high) for i, c in enumerate(window)]
        low_i, low_v = min(lows, key=lambda x: x[1])
        high_i, high_v = max(highs, key=lambda x: x[1])
        if low_i == high_i:
            return None

        size = high_v - low_v
        if size <= 0 or size / window[-1].close < self.min_push_pct:
            return None

        up = high_i > low_i  # the high came after the low, so the push went up

        # The retracement runs back from the end of the push toward its start.
        if up:
            near = high_v - size * self.fib_near
            far = high_v - size * self.fib_far
        else:
            near = low_v + size * self.fib_near
            far = low_v + size * self.fib_far

        return Push(low=low_v, high=high_v, up=up, zone_near=near, zone_far=far)

    def _ma_agrees(self, candles: list[Candle], up: bool) -> bool:
        """"the MA is our crossing over on the h4... crossed over on the 15"."""
        if self.ma_fast <= 0 or self.ma_slow <= 0:
            return True
        closes = [c.close for c in candles]
        fast = ema(closes, self.ma_fast)
        slow = ema(closes, self.ma_slow)
        if not fast or not slow or fast[-1] is None or slow[-1] is None:
            return True
        return (fast[-1] > slow[-1]) if up else (fast[-1] < slow[-1])

    def _higher_tf_agrees(self, candles: list[Candle], up: bool) -> bool:
        """"we already know the h4 shown bullish"."""
        if self.higher_tf_bars <= 0 or len(candles) < self.higher_tf_bars:
            return True
        htf = candles[-self.higher_tf_bars:]
        first = htf[: len(htf) // 2]
        last = htf[len(htf) // 2:]
        a = sum(c.close for c in first) / len(first)
        b = sum(c.close for c in last) / len(last)
        return (b > a) if up else (b < a)

    # -- the rules -------------------------------------------------------

    def evaluate(self, context: StrategyContext) -> list[Action]:
        candles = context.candles
        if len(candles) < max(self.push_bars, self.higher_tf_bars, self.ma_slow) + 5:
            return []
        if context.has_position:
            return []
        if context.risk.trades_today(self.name) >= self.max_trades_per_day:
            return []
        if (self.max_losses_per_day > 0
                and context.risk.losses_today(self.name) >= self.max_losses_per_day):
            return []
        if context.news is not None and context.news.active:
            return []

        push = self._push(candles)
        if push is None:
            return []

        if not self._higher_tf_agrees(candles, push.up):
            return []
        if not self._ma_agrees(candles, push.up):
            return []

        # "you see a double top like why is this your entry... take my Fibonacci"
        if self.require_double:
            pattern = double_top_bottom(candles)
            if pattern is None:
                return []
            # An M tops out a push up; a W bottoms a push down.
            if pattern.is_top != push.up:
                return []

        # "lower lows higher high on our macd... price is bound to reverse"
        if self.require_macd_divergence:
            div = macd_divergence(candles)
            if div == 0 or (div > 0) != push.up:
                return []

        bar = candles[-1]

        if push.up:
            # Push went up; price pulls back into the gold zone and is refused.
            # "we wait for it to come back and reject our gold zone" -- the bar
            # must REACH the zone and close back above it. A close below 0.618 is
            # the zone breaking, and he says outright that is when he is not fine.
            top, bottom = push.zone_near, push.zone_far
            if not (bar.low <= top and bar.close > bottom):
                return []
            stop = push.low - push.low * self.stop_beyond_pct
            if stop >= bar.close:
                return []
            risk = bar.close - stop
            return [Enter(side=OrderSide.BUY, stop_loss=stop,
                          take_profit=bar.close + risk * self.reward,
                          comment=self.name)]

        # Push went down; price rallies into the gold zone and is refused.
        bottom, top = push.zone_near, push.zone_far
        if not (bar.high >= bottom and bar.close < top):
            return []
        stop = push.high + push.high * self.stop_beyond_pct
        if stop <= bar.close:
            return []
        risk = stop - bar.close
        return [Enter(side=OrderSide.SELL, stop_loss=stop,
                      take_profit=bar.close - risk * self.reward,
                      comment=self.name)]
