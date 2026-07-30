"""MambaFX's "super scalper" — the strategy he builds from a blank chart.

From the video where he sets up every indicator on screen and reads out every
value, then walks a trade start to finish. It is the most completely specified
thing in his catalogue, and several of its parts existed nowhere in this project.

His setup, in his words:

    "when we use the strategy, we need to set up two things. Okay, that's just two
    simple moving averages... You're going to make it a 50 simple moving average.
    Go ahead and make it red... Then you're going to take another moving average
    and you're going to go ahead and make this a eight. Okay, I make it blue...
    You now have a eight and a 50 moving average on your screen. That's all we're
    going to be using."

    "simple ones are a lot better by the way, but I use the moving averages and I
    use momentum."

His level, which is NOT a swing high or low:

    "support and resistance is not always going to be what you think it is... all
    it really is, it's just a buildup. When you have a buildup in a zone on a H4, a
    lot of times it's going to get respected."

His timeframe stack:

    "we're going to be based upon higher time frame support resistances... and then
    smaller time frame entries."
    "right here, H4, we have a support buildup."
    "Looking at our daily, nothing's telling us that we're selling... we check our
    daily to make sure that that's the case."
    "Looking at our weekly, we actually may be coming to a support as well, which
    is good confluence."
    "don't use the hourly as much."
    "We are now going to go to our 5 minute and we're going to go ahead and see if
    we can get a moving average crossover."

His crossover, stated from the 50's point of view:

    "Anytime we see our 50 moving average cross over above... It crossed above our
    8 moving average. We're looking for sells."
    "if this 50 moving average can come below our 8 moving average, cross below
    here, and then start to swoop to the upside... we're going to be looking for
    buys."

His momentum, which he flags as the important part:

    "what are our moving averages doing here, guys? And this is very important to
    pay attention to... They're coming down and they're swooping... Once they start
    to turn up, most the time this momentum is going to pull all the way to the
    upside, okay? Because they're CURVING."

His trigger:

    "We just need to get some bullish candles just like that. Okay, there we have
    our trade. Why do we take this trade here and not here? Because we're still
    kind of coming down here. We haven't shown a bullish move... but now we have.
    This is a very big engulfing candle. So, we're going to go and take our buy
    position right here."

His stop and target:

    "we're going to put our stops below that previous support line. Okay, 17 pips.
    And we're going to target a 1:1 ratio."
    "if you want to really get technical and break this down, we could have went to
    our H4 and we could have targeted some type of zone... and then actually went
    for, you know, 1 to six."

And his market, which he is emphatic about:

    "Remember, this is only GJ, okay? You can try to back test this on other pairs.
    Will it work? It may... but me personally, GJ is my [thing] and uh it's pretty
    much what I'm going to be trading for the rest of my life."

GJ is GBPJPY. Every value below is his. The only thing chosen here is how many
bars express "curving", because he shows it rather than counting it.
"""

from __future__ import annotations

from datetime import timedelta, timezone

from ..brokers.base import Candle, OrderSide
from ..data.indicators import sma
from .base import Action, AdjustStop, Enter, Exit, Strategy, StrategyContext
from .mamba import SESSION_OPENS_UTC
from .mamba_patterns import big_candle, buildup_zone, ma_curve


class MambaScalper(Strategy):
    """His 8/50 crossover scalp off an H4 buildup, triggered by a big candle.

    Args:
        ma_fast: 8. "make this a eight... a eight blue simple moving average."
        ma_slow: 50. "make it a 50 simple moving average."
        require_curve: Whether the averages must be swooping the right way. "this
            is very important to pay attention to."
        require_engulfing: Whether a big candle is needed to pull the trigger.
            "This is a very big engulfing candle. So, we're going to go and take
            our buy position right here."
        require_buildup: Whether an H4 buildup zone must be present. "H4 buildup,
            broke it down to our 5 minute."
        daily_bars: Bars forming the daily view whose job is only to veto. "we
            check our daily to make sure that that's the case." Zero disables.
        reward: 1.0. "we're going to target a 1:1 ratio... this is just a simple
            1:1."
        max_hold_minutes: 35, his usual. "you get in, you get out, you move on."
        session: His New York window; he trades this one at the same time as the
            rest. Empty string trades around the clock.
        max_trades_per_day: 3.
        max_losses_per_day: 2.
    """

    name = "mamba_scalper"
    timeframe = "5m"
    lookback = 400

    def __init__(
        self,
        ma_fast: int = 8,
        ma_slow: int = 50,
        require_curve: bool = True,
        require_engulfing: bool = True,
        require_buildup: bool = True,
        daily_bars: int = 0,
        reward: float = 1.0,
        zone_pct: float = 0.0004,
        max_stop_pct: float = 0.00087,
        clamp_stop: bool = True,
        max_hold_minutes: int = 35,
        session: str = "newyork",
        # HIS WINDOW, HIS NUMBER: "6:30 a.m. Pacific Standard time is the only
        # time you take these trades... you do not take one before that, and you
        # only look **MAYBE AN HOUR, HOUR AND A HALF** into that session to take
        # that trade." 90 minutes. My 210 let the bot trade for three and a half
        # hours after an open he says closes in ninety minutes.
        #
        # Measured against his own entries in that video: 06:50, 06:45 and 07:05
        # Pacific -- 15 to 35 minutes past 6:30, comfortably inside ninety.
        window_minutes: int = 90,
        max_trades_per_day: int = 3,
        max_losses_per_day: int = 2,
        breakeven_at: float = 2.0,
        arm_bars: int = 12,
    ) -> None:
        self.ma_fast = ma_fast
        self.ma_slow = ma_slow
        self.require_curve = require_curve
        self.require_engulfing = require_engulfing
        self.require_buildup = require_buildup
        self.daily_bars = daily_bars
        self.reward = reward
        # "we're going to put our stops below that PREVIOUS SUPPORT LINE. Okay,
        # 17 PIPS." On GBPJPY at 195 that is 0.087% of price -- a nearby level,
        # not a session extreme.
        #
        # This was 24 bars, which on 5m is the two-hour low: about 80 pips on
        # GBPJPY, nearly five times his stop. On a $150 account that made every
        # trade unsizeable -- the sizer wanted 0.0003 lots against a 0.01 minimum
        # and refused all 14 valid setups. His tight stop is not a preference
        # here, it is what makes a small account able to take the trade at all.
        self.zone_pct = zone_pct
        # His own width. "we're going to put our stops below that previous support
        # line. Okay, 17 PIPS" -- on GBPJPY at 195 that is 0.087% of price.
        self.max_stop_pct = max_stop_pct
        # When the nearest structure sits wider than his width, does he skip the
        # trade or put the stop at his width anyway? He describes placing it "below
        # that previous support line" and reports 17 pips, so the width is the
        # thing he keeps. Rejecting instead made his 1:1 target unreachable: at a
        # 0.25% stop every trade closed on the 35-minute clock and 1:1, 1:3 and
        # 1:6 all returned identical results, because neither side was ever hit.
        # Clamping to his width is what lets his target exist at all.
        self.clamp_stop = clamp_stop
        self.max_hold_minutes = max_hold_minutes
        self.session = session
        self.window_minutes = window_minutes
        self.max_trades_per_day = max_trades_per_day
        self.max_losses_per_day = max_losses_per_day
        self.breakeven_at = breakeven_at
        # He does NOT take the trade on the crossover bar. The crossover arms the
        # setup and he then waits for price to confirm:
        #
        #   "That would be a beautiful setup. And that's all we're going to wait
        #    for, right? STILL WOULD LIKE TO SEE IT BREAK ABOVE A BIT BEFORE WE
        #    TAKE A BUY ENTRY here. But okay, right here we start to break above.
        #    We just need to get some bullish candles just like that. Okay, THERE
        #    WE HAVE OUR TRADE."
        #
        # Requiring the crossover, the swoop, the buildup and the big candle all on
        # the same bar gives literally zero trades in 6,600 samples of his own pair
        # -- the funnel goes 3.03% for the cross, 0.68% with the swoop, 0.06% with
        # the buildup, 0.00% with the candle. That is not his strategy being
        # unprofitable, it is me collapsing a sequence into an instant.
        #
        # So the cross plus the swoop ARM the setup, and it stays armed for this
        # many bars waiting for the candle that fires it.
        self.arm_bars = arm_bars

    # -- his conditions ---------------------------------------------------

    def _crossed(self, candles: list[Candle]) -> int:
        """The 8 crossing the 50 on this bar. +1 buy, -1 sell, 0 no cross.

        He phrases it from the 50: "anytime we see our 50 moving average cross
        over above... we're looking for sells", and the 50 above the 8 is the 8
        below the 50, so a buy is the 8 crossing up through the 50.
        """
        closes = [c.close for c in candles]
        fast = sma(closes, self.ma_fast)
        slow = sma(closes, self.ma_slow)
        if len(fast) < 2 or len(slow) < 2:
            return 0
        if any(v is None for v in (fast[-1], fast[-2], slow[-1], slow[-2])):
            return 0
        was = fast[-2] > slow[-2]
        now = fast[-1] > slow[-1]
        if was == now:
            return 0
        return 1 if now else -1

    def _daily_allows(self, candles: list[Candle], direction: int) -> bool:
        """"we check our daily to make sure that that's the case."

        Its job is only to say "there's nothing that says we cannot take a buy
        here" -- a veto, not a signal. So it blocks only when it actively
        disagrees.
        """
        if self.daily_bars <= 0 or len(candles) < self.daily_bars:
            return True
        window = candles[-self.daily_bars:]
        first = window[: len(window) // 2]
        last = window[len(window) // 2:]
        a = sum(c.close for c in first) / len(first)
        b = sum(c.close for c in last) / len(last)
        if b > a:
            return direction > 0
        if b < a:
            return direction < 0
        return True

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

    # -- the rules --------------------------------------------------------

    def evaluate(self, context: StrategyContext) -> list[Action]:
        candles = context.candles
        if len(candles) < self.ma_slow + 60:
            return []

        # Managing what is open comes before every entry gate.
        if self.max_hold_minutes > 0:
            for pos in context.open_positions:
                if pos.comment != self.name:
                    continue
                held = (context.now - pos.opened_at).total_seconds() / 60
                if held >= self.max_hold_minutes:
                    return [Exit(ticket=pos.ticket, reason="time-exit")]

        if self.breakeven_at > 0:
            for pos in context.open_positions:
                if pos.comment != self.name or pos.stop_loss is None:
                    continue
                risk = abs(pos.entry_price - pos.stop_loss)
                if risk <= 0:
                    continue
                price = context.bid if pos.is_long else context.ask
                ahead = ((price - pos.entry_price) if pos.is_long
                         else (pos.entry_price - price))
                if ahead < risk * self.breakeven_at:
                    continue
                done = (pos.stop_loss >= pos.entry_price if pos.is_long
                        else pos.stop_loss <= pos.entry_price)
                if not done:
                    return [AdjustStop(ticket=pos.ticket,
                                       stop_loss=pos.entry_price,
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
        if not self._in_session(context.now):
            return []

        # 1 and 2. The crossover and the swoop, looked for over the last
        #    `arm_bars` rather than only on this bar -- he waits after the cross.
        direction = 0
        for back in range(self.arm_bars):
            window = candles[:len(candles) - back] if back else candles
            if len(window) < self.ma_slow + 5:
                break
            crossed = self._crossed(window)
            if crossed != 0:
                direction = crossed
                break
        if direction == 0:
            return []

        # The swoop is checked NOW, not at the cross. His sequence is explicit:
        # "if this 50 moving average can come below our 8 moving average, CROSS
        # BELOW HERE, AND THEN START TO SWOOP to the upside... we're going to be
        # looking for buys."
        #
        # Checking it at the cross bar cannot work: at an upward cross the fast
        # average is already rising, so "was falling, now rising" is false by
        # construction. That made the strategy unfireable -- 107 armed setups and
        # zero trades. The swoop is what he waits for AFTER the cross.
        if self.require_curve and ma_curve(candles, period=self.ma_fast) != direction:
            return []

        # The averages must still be the right way round now, or the setup that
        # was armed has already expired.
        closes = [c.close for c in candles]
        fast_now = sma(closes, self.ma_fast)
        slow_now = sma(closes, self.ma_slow)
        if fast_now and slow_now and fast_now[-1] is not None and slow_now[-1] is not None:
            still = 1 if fast_now[-1] > slow_now[-1] else -1
            if still != direction:
                return []

        # 3. The H4 buildup. "H4 buildup, broke it down to our 5 minute."
        if self.require_buildup and buildup_zone(candles) is None:
            return []

        # 4. The daily's veto.
        if not self._daily_allows(candles, direction):
            return []

        # 5. The trigger. "We just need to get some bullish candles just like
        #    that... This is a very big engulfing candle. So, we're going to go and
        #    take our buy position right here."
        #
        #    Judged on SIZE, not on swallowing the previous bar. The textbook
        #    engulfing agreed with none of his 31 armed setups on GBPJPY 5m, which
        #    made the whole strategy unfireable -- his emphasis is "look at the
        #    size of this candle", not the two-bar pattern.
        if self.require_engulfing and big_candle(candles) != direction:
            return []

        bar = candles[-1]
        # "that last candle where we broke, the high of that candle" -- his
        # stop is the trigger candle's own extreme. stop_bars=3 was mine.
        window = candles[-1:]
        # "we're going to put our stops below that previous support line."
        if direction > 0:
            structure = min(c.low for c in window)
            stop = structure - structure * self.zone_pct
            if stop >= bar.close:
                return []
            risk = bar.close - stop
            # "super, super tight stop losses"
            if self.max_stop_pct > 0 and risk > bar.close * self.max_stop_pct:
                if not self.clamp_stop:
                    return []
                stop = bar.close - bar.close * self.max_stop_pct
                risk = bar.close - stop
            return [Enter(side=OrderSide.BUY, stop_loss=stop,
                          take_profit=bar.close + risk * self.reward,
                          comment=self.name)]

        structure = max(c.high for c in window)
        stop = structure + structure * self.zone_pct
        if stop <= bar.close:
            return []
        risk = stop - bar.close
        if self.max_stop_pct > 0 and risk > bar.close * self.max_stop_pct:
            if not self.clamp_stop:
                return []
            stop = bar.close + bar.close * self.max_stop_pct
            risk = stop - bar.close
        return [Enter(side=OrderSide.SELL, stop_loss=stop,
                      take_profit=bar.close - risk * self.reward,
                      comment=self.name)]
