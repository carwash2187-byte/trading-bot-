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
from ..data.indicators import sma
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
        (push_bars and min_push_pct deleted. He gives NEITHER a lookback nor a
        minimum size -- his rule is "I'm drawing it from that MAIN PUSH, where the
        market structure really starts to go" and "the push is not down in here
        because YEAH IT PUSH, BUT THEN IT CAME BACK DOWN -- this is where the main
        push is". The walk-back below already stops itself on exactly that: it
        breaks the moment price retraces more than half the progress made. A leg
        that survives that test IS his main push, whatever its size and however far
        back it started. My 60-bar window truncated legs he would have kept, and my
        0.4% floor threw away legs he never measured.)

        (removed: how large the move must be, as a fraction of price, before
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
        fib_near: float = 0.5,
        fib_far: float = 0.618,
        fib_stop: float = 0.764,
        ma_fast: int = 8,
        ma_slow: int = 50,
        higher_tf_bars: int = 96,
        reward: float = 3.0,
        stop_beyond_pct: float = 0.0008,
        max_trades_per_day: int = 2,
        max_losses_per_day: int = 2,
        require_double: bool = False,
        require_macd_divergence: bool = False,
    ) -> None:
        self.fib_near = fib_near
        self.fib_far = fib_far
        # 0.764, NOT the standard 0.786. Read off his tool on five separate draws,
        # and verified arithmetically against the printed prices. It is coloured
        # black on his template while 0.5 is gold and 0.618 is orange -- so it is
        # not part of the entry zone, it is where the stop goes. Measured: two of
        # his four stops sat within 1.8 pips of this line.
        #
        # That replaces stop_beyond_pct, which was a distance I invented. His stop
        # is a fib level, so it needs no width of mine.
        self.fib_stop = fib_stop
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

    def _push_from(self, candles: list[Candle], end_i: int,
                   up: bool) -> Push | None:
        """The impulse to measure across -- the LAST CLEAN one, not the biggest.

        He states this rule twice and it is the whole skill as he presents it:

            "the way I'm drawing my Fibonacci's is very simple, I'm drawing it from
             that MAIN PUSH. So I'm not gonna draw my Fibonacci from here to up
             here -- no. I'm gonna draw it from where the MARKET STRUCTURE REALLY
             STARTS TO GO."

            "this push starts here, it doesn't start down in that area... the push
             is not down in here, because YEAH IT PUSH, BUT THEN IT CAME BACK
             DOWN. This is where the main push is."

        Measured on his own chart: he anchored at 107.283 while the actual low in
        view was ~106.75 -- deliberately skipping 53 pips of larger move. This
        method previously took the extreme low and extreme high of the window,
        which is exactly the "here to up here" he refuses.

        So: walk back from the current bar to the most recent swing that started a
        one-directional run, and stop as soon as the run is broken by a meaningful
        pullback. An origin that pushed and then came back down is disqualified.

        And "it is kind of steep... don't really have much rejections" -- he passes
        on a leg too vertical to have left wicks behind, which is why a leg needs
        enough bars to have structure rather than merely enough size.
        """
        # No window of mine: the walk-back terminates on his own rule.
        window = candles
        if len(window) < 15:
            return None

        last = window[-1]

        # Walk back while the run holds. It breaks when price retraces more than
        # `break_frac` of the progress made so far -- that is the "it came back
        # down" he names.
        # HIS DISQUALIFICATION, MEASURED PROPERLY.
        #
        #   "the push is not down in here, because YEAH IT PUSH, BUT THEN IT CAME
        #    BACK DOWN. this is where the main push is."
        #
        # An earlier origin is wrong when the move from it already pushed and gave
        # the ground back. So each candidate origin is tested by the DEEPEST
        # PULLBACK inside the leg it would create: if price ever handed back more
        # than half of what it had made, that origin contains a "came back down"
        # and the last good one stands.
        #
        # The previous version compared the leg high against the highest high from
        # the candidate onwards, which is not a retracement at all -- it shrinks as
        # you walk back, so the loop broke almost immediately. push_bars=60 kept
        # the damage inside a small window and hid it. Unbounded, it fired 3 times
        # in 3,920 with stops ten times his width, which is how the bug surfaced.
        # HIS RULE, AND IT MOVES THE ORIGIN FORWARD RATHER THAN WALKING BACK.
        #
        #   "the push is not down in here, because YEAH IT PUSH, BUT THEN IT CAME
        #    BACK DOWN. THIS is where the main push is."
        #
        # He starts from the furthest origin, notices the leg contains a big
        # retracement, and slides the start forward to AFTER it. So: take the
        # extreme before the swing, measure the deepest drawdown inside the leg,
        # and if it handed back more than half, restart the leg at that drawdown's
        # low. Repeat until the leg is clean.
        #
        # The previous walk-back tested candidate origins one bar at a time and
        # broke on the FIRST one, because a two-bar leg always pulls back more than
        # half of itself -- so it returned None every single time (0 of 62 swing
        # highs). That is what made the whole strategy silent.
        break_frac = 0.5

        def deepest(seg: list, upward: bool) -> tuple[float, int]:
            """Biggest giveback inside the segment, and where it bottomed."""
            worst, at = 0.0, 0
            if upward:
                peak = seg[0].high
                for k, c in enumerate(seg):
                    peak = max(peak, c.high)
                    if peak - c.low > worst:
                        worst, at = peak - c.low, k
            else:
                trough = seg[0].low
                for k, c in enumerate(seg):
                    trough = min(trough, c.low)
                    if c.high - trough > worst:
                        worst, at = c.high - trough, k
            return worst, at

        if up:
            end_v = window[end_i].high
            origin = min(range(end_i + 1), key=lambda k: window[k].low)
            for _ in range(20):
                leg = end_v - window[origin].low
                if leg <= 0:
                    return None
                worst, at = deepest(window[origin:end_i + 1], True)
                if worst / leg <= break_frac or at == 0:
                    break
                origin = origin + at        # "this is where the main push is"
            low_v, high_v = window[origin].low, end_v
            low_i, high_i = origin, end_i
        else:
            end_v = window[end_i].low
            origin = max(range(end_i + 1), key=lambda k: window[k].high)
            for _ in range(20):
                leg = window[origin].high - end_v
                if leg <= 0:
                    return None
                worst, at = deepest(window[origin:end_i + 1], False)
                if worst / leg <= break_frac or at == 0:
                    break
                origin = origin + at
            low_v, high_v = end_v, window[origin].high
            low_i, high_i = end_i, origin

        if low_i == high_i:
            return None
        size = high_v - low_v
        if size <= 0:
            return None

        # The retracement runs back from the end of the push toward its start.
        if up:
            near = high_v - size * self.fib_near
            far = high_v - size * self.fib_far
        else:
            near = low_v + size * self.fib_near
            far = low_v + size * self.fib_far

        return Push(low=low_v, high=high_v, up=up, zone_near=near, zone_far=far)

    def _push(self, candles: list[Candle]) -> Push | None:
        """The swing whose gold zone price is sitting in RIGHT NOW.

        "we wait for it to come back and REJECT OUR GOLD ZONE."

        That sentence is the selection rule, and it needs no lookback window. He
        does not pick a swing and then hope price visits its zone -- he watches the
        zone price is currently in. So every recent swing extreme is a candidate
        and the one that matters is the most recent whose 0.5-0.618 band the
        current bar is actually touching.

        Anchoring to a single extreme instead (the highest bar in the window) is
        what produced ZERO entries in 2,000 bars: by the time that bar is the
        highest of 350, price has usually retraced far past its zone. The gate
        counts showed it exactly -- 32 setups survived every other test and 0 were
        in the zone.
        """
        if len(candles) < 15:
            return None
        bar = candles[-1]
        n = len(candles)
        # Swing extremes, minimally defined: higher than the bar either side. That
        # is structure, not a tuned parameter -- there is no width to choose.
        for i in range(n - 3, 2, -1):
            c = candles[i]
            if c.high > candles[i - 1].high and c.high > candles[i + 1].high:
                push = self._push_from(candles, i, True)
                if push is not None and bar.low <= push.zone_near \
                        and bar.close > push.zone_far:
                    return push
            if c.low < candles[i - 1].low and c.low < candles[i + 1].low:
                push = self._push_from(candles, i, False)
                if push is not None and bar.high >= push.zone_near \
                        and bar.close < push.zone_far:
                    return push
        return None

    def _ma_agrees(self, candles: list[Candle], up: bool) -> bool:
        """"the MA is our crossing over on the h4... crossed over on the 15".

        His pair is 8 and 50, SIMPLE: "you now have a eight and a 50 moving
        average on your screen. That's all we're going to be using", and "simple
        ones are a lot better by the way". This file previously used exponential
        9 and 21, which were mine.
        """
        if self.ma_fast <= 0 or self.ma_slow <= 0:
            return True
        closes = [c.close for c in candles]
        fast = sma(closes, self.ma_fast)
        slow = sma(closes, self.ma_slow)
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
        if len(candles) < max(self.higher_tf_bars, self.ma_slow) + 20:
            return []
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
            # "a nice little stop-loss just below where a wick" -- and measured,
            # that lands on his 0.764. The fib supplies it; no width of mine.
            size = push.high - push.low
            stop = push.high - size * self.fib_stop
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
        size = push.high - push.low
        stop = push.low + size * self.fib_stop
        if stop <= bar.close:
            return []
        risk = stop - bar.close
        return [Enter(side=OrderSide.SELL, stop_loss=stop,
                      take_profit=bar.close - risk * self.reward,
                      comment=self.name)]
