"""The patterns decide the trade — buy or sell comes from what the chart shows.

Leo's correction, and he is right: these patterns are not decoration on top of a
direction worked out some other way. They ARE how he decides. Each one points a
way, and he says so every time he names one.

    "whenever the market makes an m uh it's pretty obvious what's going to happen
    right we have a double top resistance"

An M means sell. He does not check anything else to learn that — the M is the
reason.

    "what i saw was a very bearish candle that just engulfed all this [stuff]
    while our moving averages are above everything i'm pretty sure the moving
    averages here are just gonna pull our trade to the downside"

A bearish engulfing candle means sell.

    "our entry came from this 4-hour liquidity sweep"

Price pushing past the old highs and failing back means sell — the stops above got
taken and there is nobody left to buy.

    "lower lows higher high on our macd all that means is that price is bound to
    reverse"

Divergence means the current direction ends.

    "We have that other fair value gap now supporting price"

A gap under price holds it up, which is a reason to buy.

So this strategy asks every pattern which way it points, and trades when they
agree. That is the whole idea: **the chart tells you the direction, and the
patterns are how you read it.**

Everything else about the trade stays as he describes it elsewhere -- New York
session only, stop past the structure, 1:3, out in about half an hour, three
trades a day, two losses ends the day.
"""

from __future__ import annotations

from datetime import timedelta, timezone

from ..data.ohlc import timeframe_minutes
from ..brokers.base import Candle, OrderSide
from ..data.indicators import sma
from .base import Action, AdjustStop, Enter, Exit, Strategy, StrategyContext
from .mamba import SESSION_OPENS_UTC
from .mamba_patterns import (
    buildup_zone,
    level_map,
    snap_to_level,
    ma_curve,
    obv_divergence,
    double_top_bottom,
    engulfing,
    fair_value_gap,
    liquidity_sweep,
)


class MambaSignals(Strategy):
    """Every pattern votes on direction; trade when enough of them agree.

    Args:
        min_votes: How many of his signals must point the same way. THREE, and
            this is the one parameter that stopped being mine: he counts them out
            loud while placing a trade.

                "we hit the bottom of a channel so we know it's gonna push to the
                 upside, we have bearish divergence showing TWO CONFIRMATIONS and
                 now in THIRD CONFIRMATION a fibonacci golden zone retest -- oh my
                 god this trade's beautiful"

            And he refuses a single one outright: "this isn't enough, we can't use
            just this as a confirmation." Elsewhere: "that's two confirmations if
            not like six." So the floor is three, not the two I had guessed.
        session: "you only trade during New York session". Empty string trades
            around the clock, which is what he does on gold and crypto.
        window_minutes: 210. "I don't like to trade much past 10:00 a.m."
        reward: 3.0. "a nice little one to three."
        max_hold_minutes: 35. "30 minutes, 35 minutes at the most."
        (stop_bars deleted -- his stop is the TRIGGER CANDLE's own extreme, so
        there is no window to size. "I like to go based off of where we broke...
        I'm going to place that just above that last candle. So that last candle
        where we broke, the high of that candle... That's where my stop loss is
        going to go." Measured on his chart: the stop sat EXACTLY on the breakout
        candle's high, and his two stops came out 48.7 and 29.5 points -- one
        candle's range, not a 24-bar swing.)
        max_trades_per_day: 3.
        max_losses_per_day: 2.
        breakeven_at: R at which the stop goes to entry, after banking half.
        scale_at: R at which half comes off.
    """

    name = "mamba_signals"
    timeframe = "5m"

    # HIS BITCOIN MASTER SWITCH, shared across every instance.
    #
    #   "everything's based around bitcoin right so right here we saw a big fall in
    #    bitcoin look at dodge we saw a very similar fall look at litecoin a similar
    #    fall and look at xrp a similar fall so just remember ANYTIME BITCOIN FALLS
    #    OR GETS PUMPED MOST OTHER CRYPTOS especially like the bigger ones based
    #    around it ARE GOING TO PUMP UP AS WELL"
    #
    # He checks Bitcoin first and treats the alts as followers. Nothing in this
    # project could express that, because the portfolio runs each market in
    # isolation and a strategy trading XRP has never been able to see BTC.
    #
    # Class-level on purpose: the instance handling BTCUSD writes its direction
    # here, and the instances handling the alts read it. That works identically in
    # the backtest and live, because both create one instance per symbol sharing
    # this class.
    _btc_bias: int = 0
    _btc_seen_at: object = None
    # Must exceed the longest window any rule asks for, or that rule silently
    # never runs. The weekly view wants 480 bars of 15m and this was 400, so
    # `weekly_bars=480` returned zero on every single bar -- the eleventh rule in
    # this project that was present, correct, and unreachable. The live cycle
    # requests exactly this many bars from the broker, so it is also the real
    # ceiling on what any rule here can look at.
    lookback = 600

    def __init__(
        self,
        min_votes: int = 3,
        his_three: bool = True,
        btc_gates_alts: bool = True,
        session: str = "newyork",
        sessions: tuple[str, ...] = (),
        window_minutes: int = 210,
        flatten_at_window_end: bool = False,
        wait_for_close: bool = True,
        reward: float = 3.0,
        max_hold_minutes: int = 35,
        use_ma_swoop: bool = True,
        ma_fast: int = 8,
        ma_slow: int = 50,
        h4_bars: int = 0,
        daily_bars: int = 0,
        allow_reentry: bool = False,
        reentry_bars: int = 24,
        higher_tf_gates: bool = True,
        max_trades_per_day: int = 2,
        max_losses_per_day: int = 2,
        stop_after_win: bool = True,
        use_ma_crossover: bool = False,
        use_buildup: bool = False,
        breakeven_at: float = 0.0,
        scale_at: float = 0.0,
        exit_on_reason_gone: bool = False,
        breakeven_pad: float = 0.0,
        max_stop_pct: float = 0.0,
        skip_if_stop_too_wide: bool = True,
        stop_at_ma: bool = False,
        fixed_lots: float | None = None,
    ) -> None:
        self.min_votes = min_votes
        self.his_three = his_three
        # "anytime bitcoin falls or gets pumped most other cryptos... are going to
        # pump up as well." An alt only trades in the direction Bitcoin is going.
        self.btc_gates_alts = btc_gates_alts
        self.session = session
        # "16 targets hit, one stop loss last week, 6 in one for London session
        # and then for Asia session, 10 in one." He trades Asia and London as
        # well as New York, and counts them separately. When this is set it
        # replaces the single `session`.
        self.sessions = sessions
        self.window_minutes = window_minutes
        # "As soon as it breaks, we're not waiting for candle to close, we're not
        # waiting for no other confirmation."
        # "i don't take trades based on closed candles i take trades based on
        # moving candles."
        #
        # So his trigger is the level being touched, not a bar closing beyond it.
        # With this False the pattern only has to have been reached during the
        # bar. The fill still happens at the bar's close, which for a breakout is
        # a WORSE price than the level itself -- so this cannot flatter the
        # result, it can only cost.
        self.wait_for_close = wait_for_close
        self.reward = reward
        self.max_hold_minutes = max_hold_minutes
        # THIRTEENTH BUG, and the first that CRASHES rather than going quiet:
        # this was a constructor argument that was never stored, so evaluate()
        # raised AttributeError the moment it reached the session check with
        # enough candles to get there. The main build would have died on the
        # live account on its first real bar.
        self.flatten_at_window_end = flatten_at_window_end
        # DELETED: the side-of-the-average vote.
        #
        # Price is always on one side of a moving average, so it voted on 100% of
        # bars -- a free vote that made a threshold of three mean "the average plus
        # any two other things". And he never asks the question it answered. He
        # does not say "price is above the 50, so buy"; he names two EVENTS, the
        # crossover and the swoop, and both are below. A state he never reads is
        # not a rule of his, so the knob is gone rather than defaulted off.
        # "what are our moving averages doing here, guys? And this is very
        #  important to pay attention to... they're SWOOPING... Once they start to
        #  turn up, most the time this momentum is going to pull all the way to the
        #  upside... Because they're CURVING."
        self.use_ma_swoop = use_ma_swoop
        # His two moving averages, read out as he builds them on a blank chart:
        #
        #   "we need to set up two things. Okay, that's just TWO SIMPLE MOVING
        #    AVERAGES."
        #   "You're going to make it a 50 SIMPLE moving average. Go ahead and make
        #    it red."
        #   "Then you're going to take another moving average and you're going to
        #    go ahead and make this a EIGHT. Okay, I make it blue... for me, it's a
        #    eight blue simple moving average."
        #   "You now have a EIGHT AND A 50 moving average on your screen. THAT'S
        #    ALL WE'RE GOING TO BE USING."
        #   "simple ones are a lot better by the way"
        #
        # I had 9 and 21, exponential. Wrong periods and wrong type -- he names 8
        # and 50, simple, and says twice that is all he uses. He mentions the 50
        # in 22 separate places across the videos and 9 or 21 in none.
        self.ma_fast = ma_fast
        self.ma_slow = ma_slow
        # "how i'm trading it is first off i need to determine are we going up are
        # we going down are we in a bullish trend or a bearish trend... and that's
        # going to be from the daily and the four hour."
        #
        # So the higher timeframes have exactly ONE job -- direction. Not levels,
        # not zones. That is why the earlier attempt at a "daily filter" failed:
        # it was measuring where price sat inside a daily range, which is not what
        # he uses the daily for.
        #
        # And he ranks them: "we're gonna start on the h4 always h4 you can use
        # the daily as well i like the h4." H4 first, daily optional.
        #
        # Counted in bars of this strategy's own timeframe. On 5m: 48 bars is 4
        # hours, 288 is a day. Zero disables either.
        # FOURTEENTH SILENT RULE, and it switched off his single hardest refusal.
        # Both of these defaulted to ZERO, and the gate below is written as
        # "if higher_tf_gates and (h4_bars > 0 or daily_bars > 0)" -- so on every
        # build except mamba_complete, the higher timeframes were never consulted
        # AT ALL. Not wired as votes. Not wired.
        #
        # What that switched off, in his own words, said twice in one video:
        #     "we CANNOT take these five-minute trades if our h4 or our daily is
        #      not in confluence telling us we're going down. we have to see that
        #      FIRST before we come down and take our cell trades"
        #
        # The counts are not numbers I picked -- they are what the words mean. Four
        # hours is 240 minutes and a day is 1440, so on any timeframe the bar count
        # is that divided by the bar length. Passing an explicit value still wins.
        tf = max(1, timeframe_minutes(self.timeframe))
        self.h4_bars = h4_bars if h4_bars > 0 else 240 // tf
        self.daily_bars = daily_bars if daily_bars > 0 else 1440 // tf
        # THE WEEKLY IS DELETED, not disabled.
        #
        # "remember guys, H4 support resistance daily and weekly." / "Looking at
        # our weekly, we actually may be coming to a support as well, which is GOOD
        # CONFLUENCE, right?" / "If we look at the weekly, we're at a 10-year
        # support."
        #
        # Every time he mentions the weekly it makes him feel better about a trade
        # he is taking anyway. It never stops him and it never starts him. A thing
        # that cannot change the decision is not a rule, and wiring it as a vote
        # among equals gave it power he never gives it -- it turned 1.36x into
        # 0.77x by outvoting the patterns that actually decide.
        #
        # So it is removed rather than defaulted off. He looks at the weekly; the
        # bot does not need to, because looking without acting is not a behaviour a
        # bot can have.
        # "trade number three was really TRADE NUMBER TWO PART TWO because it's
        #  still the same move we're still going up on the same day and I decided
        #  I GOT OUT TOO EARLY I WANT TO RE-ENTER this trade."
        # "I'm going to go ahead and RE-ENTER LONGS right now."
        # "now that we did break some highs, I think I MIGHT JUST REENTER longs."
        # "I would RE-ENTER for a buy" (once price pushes back through the level)
        #
        # He goes again when he left too early and the move is still running. He
        # does NOT re-enter after being stopped out -- every re-entry he narrates
        # follows a manual exit, never a stop. So this only arms after the bot
        # closed on the clock or because the reason died.
        self.allow_reentry = allow_reentry
        self.reentry_bars = reentry_bars
        # Set when a position is closed manually, so the next bars can go again.
        self._reentry_armed: int | None = None
        self._reentry_side: int = 0
        # His ORDER matters, not just his ingredients. "first off i need to
        # determine are we going up are we going down... and that's going to be
        # from the daily and the four hour." Direction is decided FIRST, by the
        # higher timeframes, and the patterns then confirm inside it. Treating
        # them as equal votes alongside the patterns is a different strategy and
        # a worse one -- it dilutes five pattern votes with two trend votes.
        self.higher_tf_gates = higher_tf_gates
        self.max_trades_per_day = max_trades_per_day
        self.max_losses_per_day = max_losses_per_day
        self.stop_after_win = stop_after_win
        # "we're going to be looking for CROSSOVERS on the 5 minute time frame"
        # "We are now going to go to our 5m and we're going to go ahead and see if
        #  we can get a moving average crossover."
        #
        # A crossover is an event, not a state -- the 8 crossing the 50 on THIS
        # bar, rather than merely sitting above it. That distinction is the whole
        # difference between a signal and a condition.
        self.use_ma_crossover = use_ma_crossover
        # His "buildup zone", which is a level shape nothing else here looks for:
        #
        #   "support and resistance is not always going to be what you think it
        #    is... all it really is, it's just a BUILDUP. When you have a buildup
        #    in a zone on a H4, a lot of times it's going to get respected."
        #   "It's just a buildup IN THE MOMENT OFF A BUNCH OF CANDLES. It's a
        #    buildup zone. It's support."
        #
        # Every other detector here hunts swing extremes -- the "solid supports"
        # he says a level is NOT always shaped like. A buildup is congestion: a
        # stack of ordinary candles in a narrow band. It is a LOCATION rather than
        # an event, so it votes only when price has come back to it and been
        # turned away, which is the "respected" part.
        self.use_buildup = use_buildup
        # "let's say we got to a 1 to two stops can go to break even and boom the
        # rest is history." Two, not one -- and every earlier test in this project
        # used one, which cut winners in half.
        self.breakeven_at = breakeven_at
        self.scale_at = scale_at
        # "I ended up closing around this area um just because I wasn't sure if
        # price was going to fully reverse here."
        # "trend got broke you know the candle is closed below it's just it's not
        # going to come back... it's not looking good."
        #
        # This is the mechanic behind a trade that goes against him and still
        # costs nothing: when the reason for being in it stops being true, he
        # leaves. He does not sit and wait to be proved wrong by the stop.
        self.exit_on_reason_gone = exit_on_reason_gone
        # "put uh stops to break even, NEAR break even" -- a shade better than
        # entry, so a scratch is fractionally green rather than exactly flat.
        # Expressed as a fraction of the original risk.
        self.breakeven_pad = breakeven_pad
        # "here's the key with the strategy, SUPER, SUPER TIGHT STOP LOSSES."
        # "I'm having a super super super tight stop loss."
        # "I want to get in very fast, tight stop loss, and I want that one to five."
        #
        # This is why his losses barely register. His stated stop sizes across the
        # videos: 10, 13, 16, 22, 25, 30, 44 pips -- against targets of 50, 51,
        # 60, 80, 250, 1000. On a 1.30 pair, 16 pips is 0.12% of price.
        #
        # "I know that if this hits a loss I'll probably lose 50 bucks if this hits
        # a win I'm gonna make 500."
        # "I had you know 10 pip loss 15 pip loss uh 10 pips and 20 pips profit."
        #
        # Expressed as a fraction of price. Zero disables.
        self.max_stop_pct = max_stop_pct
        # When the structural stop comes out wider than his cap, does he skip the
        # trade or tighten the stop? He says he WANTS tight stops, which reads as
        # picking setups that offer them -- so skipping is the default. Tightening
        # instead is available because a tight stop on a wide structure is still a
        # trade he might take with a mental stop.
        self.skip_if_stop_too_wide = skip_if_stop_too_wide
        # "have our stops just below our moving average because price pretty much
        # respects it as a support" / "stops are gonna be just below that moving
        # average". A stop location I had not built.
        self.stop_at_ma = stop_at_ma
        # "if you're using a 0.01 that would have been a dollar sixty loss for a
        # five dollar and 10 cent gain."
        #
        # A fixed lot is what makes his losses look like nothing happened. Under
        # percentage sizing a tight stop buys more lots and the cash loss is
        # unchanged; under a fixed lot the tight stop IS the small loss. On a $150
        # account at 0.01 lots, a 16-pip stop costs 1.07% and a 10-pip stop 0.67%,
        # against a flat 2% however wide the stop is.
        self.fixed_lots = fixed_lots

    # -- asking each pattern which way it points -------------------------

    def votes(self, candles: list[Candle]) -> dict[str, int]:
        # The engulfing test is the one vote that depends on a completed bar, so
        # when he is not waiting for the close it is read from the bar so far.

        """What every pattern says. +1 buy, -1 sell, 0 no opinion."""
        out: dict[str, int] = {}

        # "whenever the market makes an m... we have a double top resistance"
        pattern = double_top_bottom(candles)
        if pattern is not None:
            out["double"] = -1 if pattern.is_top else 1

        # "a very bearish candle that just engulfed all this"
        eng = engulfing(candles)
        if eng:
            out["engulfing"] = eng

        # "our entry came from this 4-hour liquidity sweep"
        swept = liquidity_sweep(candles)
        if swept:
            out["sweep"] = swept

        # "from here to here lower low, look at the obv higher low -- that is a
        # huge sign of reversal." OBV is what is actually loaded on his chart,
        # visible in the legend beside EMA 8 and MA 21.
        odiv = obv_divergence(candles)
        if odiv:
            out["obv"] = odiv

        # DELETED: MACD divergence. It entered this project on a single passing
        # mention -- "lower lows higher high on our macd" -- while OBV is what is
        # actually in his chart legend and what he points at while explaining a
        # trade. Two divergence signals voting is one of them inventing weight he
        # never gives it.

        # "when you have a buildup in a zone on a H4, a lot of times it's going
        # to get respected" -- the vote is price returning to the zone and being
        # refused, not the zone merely existing.
        if self.use_buildup:
            zone = buildup_zone(candles)
            if zone is not None:
                bar = candles[-1]
                touched_below = bar.low <= zone.high and bar.close > zone.high
                touched_above = bar.high >= zone.low and bar.close < zone.low
                if touched_below:
                    out["buildup"] = 1     # came down to it and held: support
                elif touched_above:
                    out["buildup"] = -1    # came up to it and failed: resistance

        # "that other fair value gap now supporting price"
        gap = fair_value_gap(candles)
        if gap is not None:
            close = candles[-1].close
            if gap[1] < close:
                out["gap"] = 1      # gap below, holding price up
            elif gap[0] > close:
                out["gap"] = -1     # gap above, capping price

        # The higher timeframes only join the vote when they are NOT acting as
        # the gate. As a gate they come first and outrank everything, which is
        # his stated order.
        if not self.higher_tf_gates:
            for key, bars in (("h4", self.h4_bars), ("daily", self.daily_bars)):
                d = self._tf_direction(candles, bars)
                if d:
                    out[key] = d

        # "this is very important to pay attention to" -- the averages bending.
        if self.use_ma_swoop:
            swoop = ma_curve(candles, period=self.ma_fast)
            if swoop:
                out["swoop"] = swoop

        # "see if we can get a moving average crossover" -- the 8 crossing the 50
        # on THIS bar, which is an event rather than a state.
        if self.use_ma_crossover:
            closes = [c.close for c in candles]
            fast = sma(closes, self.ma_fast)
            slow = sma(closes, self.ma_slow)
            if (len(fast) > 1 and len(slow) > 1
                    and None not in (fast[-1], fast[-2], slow[-1], slow[-2])):
                was = fast[-2] > slow[-2]
                now = fast[-1] > slow[-1]
                if was != now:
                    out["ma_cross"] = 1 if now else -1

        return out

    def _tf_direction(self, candles: list[Candle], bars: int) -> int:
        """Up or down over ``bars``. Zero when disabled or flat."""
        if bars <= 0 or len(candles) < bars:
            return 0
        window = candles[-bars:]
        first = window[: len(window) // 2]
        last = window[len(window) // 2:]
        a = sum(c.close for c in first) / len(first)
        b = sum(c.close for c in last) / len(last)
        if b > a:
            return 1
        if b < a:
            return -1
        return 0

    def _higher_tf_gate(self, candles: list[Candle]) -> int:
        """"first off i need to determine are we going up are we going down...
        that's going to be from the daily and the four hour."

        He prefers the H4 -- "always h4 you can use the daily as well i like the
        h4" -- so the H4 decides and the daily may only veto by disagreeing.
        Returns 0 when there is no usable opinion, which means no trade.
        """
        h4 = self._tf_direction(candles, self.h4_bars)
        daily = self._tf_direction(candles, self.daily_bars)
        if self.h4_bars > 0 and self.daily_bars > 0:
            if h4 == 0 or daily == 0 or h4 != daily:
                return 0
            return h4
        return h4 or daily

    def _in_session(self, now) -> bool:
        names = self.sessions or ((self.session,) if self.session else ())
        if not names:
            return True
        utc = now.astimezone(timezone.utc)
        for name in names:
            open_at = SESSION_OPENS_UTC.get(name)
            if open_at is None:
                continue
            start = utc.replace(hour=open_at.hour, minute=open_at.minute,
                                second=0, microsecond=0)
            if start <= utc <= start + timedelta(minutes=self.window_minutes):
                return True
        return False

    # -- the rules -------------------------------------------------------

    def evaluate(self, context: StrategyContext) -> list[Action]:
        candles = context.candles
        if len(candles) < 80:
            return []

        # "getting a little later in the day... pack the books." When his window
        # shuts, open trades go -- he does not carry a scalp past his own session.
        if self.flatten_at_window_end and not self._in_session(context.now):
            for pos in context.open_positions:
                if pos.comment == self.name:
                    return [Exit(ticket=pos.ticket, reason="window-closed")]

        # Managing what is open comes before any entry gate, always.
        if self.max_hold_minutes > 0:
            for pos in context.open_positions:
                if pos.comment != self.name:
                    continue
                held = (context.now - pos.opened_at).total_seconds() / 60
                if held >= self.max_hold_minutes:
                    # "I got out too early I want to re-enter this trade" -- a
                    # clock exit is exactly the case he goes back into.
                    if self.allow_reentry:
                        self._reentry_armed = 0
                        self._reentry_side = 1 if pos.is_long else -1
                    return [Exit(ticket=pos.ticket, reason="time-exit")]

        # "I ended up closing... just because I wasn't sure if price was going to
        # fully reverse" / "trend got broke... it's not going to come back".
        # Checked before the profit-taking rules, because the reason dying is a
        # reason to leave regardless of where the trade currently sits.
        if self.exit_on_reason_gone:
            for pos in context.open_positions:
                if pos.comment != self.name:
                    continue
                v = self.votes(candles)
                if not v:
                    continue
                buys = sum(1 for x in v.values() if x > 0)
                sells = sum(1 for x in v.values() if x < 0)
                now_says = 1 if buys > sells else (-1 if sells > buys else 0)
                held = 1 if pos.is_long else -1
                # Only leave when the chart has actively turned against the
                # trade, not merely gone quiet.
                if now_says != 0 and now_says != held:
                    if self.allow_reentry:
                        self._reentry_armed = 0
                        self._reentry_side = held
                    return [Exit(ticket=pos.ticket, reason="reason-gone")]

        for pos in context.open_positions:
            if pos.comment != self.name or pos.stop_loss is None:
                continue
            risk = abs(pos.entry_price - pos.stop_loss)
            if risk <= 0:
                continue
            price = context.bid if pos.is_long else context.ask
            ahead = ((price - pos.entry_price) if pos.is_long
                     else (pos.entry_price - price))
            banked = (pos.stop_loss >= pos.entry_price if pos.is_long
                      else pos.stop_loss <= pos.entry_price)
            # Half off first, then the stop to entry -- his order, from
            # "take profit one right there did get smashed okay we would have our
            # stops at break even".
            if self.scale_at > 0 and not banked and ahead >= risk * self.scale_at:
                half = round(pos.lots / 2, 2)
                if half >= 0.01 and pos.lots > 0.01:
                    return [Exit(ticket=pos.ticket, lots=half, reason="half-off")]
            if self.breakeven_at > 0 and not banked and ahead >= risk * self.breakeven_at:
                # "stops to break even, NEAR break even" -- a shade the right side
                # of entry. And a stop only ever moves toward profit: he never
                # once mentions widening one, in 144 transcripts.
                pad = risk * self.breakeven_pad
                want = (pos.entry_price + pad if pos.is_long
                        else pos.entry_price - pad)
                better = (want > pos.stop_loss if pos.is_long
                          else want < pos.stop_loss)
                if better:
                    return [AdjustStop(ticket=pos.ticket, stop_loss=want,
                                       take_profit=pos.take_profit)]

        if context.has_position:
            return []
        if context.risk.trades_today(self.name) >= self.max_trades_per_day:
            return []
        # HE CONTRADICTS HIMSELF ON THIS ONE, SO IT IS A SWITCH RATHER THAN AN
        # ASSUMPTION. Both quotes are his:
        #
        #   FOR:     "First trade works out, WE'RE DONE. We don't go for a second.
        #             First trade doesn't work out, we look for a second one."
        #   AGAINST: "whether it's two losses, TWO WINS, or one of each. Take your
        #             two trades, you're done."
        #
        # The second was confirmed by two independent viewings of the same video.
        # What all three videos agree on is the TWO-TRADE CAP above, which is why
        # that one is unconditional and this one is a flag.
        if self.stop_after_win and context.risk.wins_today(self.name) >= 1:
            return []
        if (self.max_losses_per_day > 0
                and context.risk.losses_today(self.name) >= self.max_losses_per_day):
            return []
        if context.news is not None and context.news.active:
            return []
        if not self._in_session(context.now):
            return []

        # "I got out too early I want to re-enter this trade." A re-entry needs
        # only the move to still be going his way, not a fresh full setup -- he
        # calls it "trade number two part two". It still counts against his day,
        # because he numbers it as a trade.
        if self.allow_reentry and self._reentry_armed is not None:
            self._reentry_armed += 1
            if self._reentry_armed > self.reentry_bars:
                self._reentry_armed = None
                self._reentry_side = 0
            else:
                v = self.votes(candles)
                b = sum(1 for x in v.values() if x > 0)
                sl = sum(1 for x in v.values() if x < 0)
                still = 1 if b > sl else (-1 if sl > b else 0)
                # He does NOT re-enter on the move merely still pointing his way:
                #
                #   "i'm not going to continue to re-enter UNLESS THAT TRADING
                #    STRATEGY SAYS IT'S STILL A GOOD TRADE right but don't over
                #    trade."
                #
                # And he names the anti-pattern he is guarding against: "you can't
                # just sit there and oh i took a 10 pip loss i'm going to re-enter
                # oh i took another 20 pip [loss] i'm going to re-enter and go for
                # a 300 pip game -- it's just not like that."
                #
                # So a re-entry needs the SAME confirmation a fresh entry needs, not
                # a weaker one. Built as: the full vote threshold must still be met,
                # not simply more votes on one side than the other.
                enough = (b if still > 0 else sl) >= self.min_votes
                if still != 0 and still == self._reentry_side and enough:
                    bar = candles[-1]
                    win = candles[-1:]     # his trigger candle
                    if still > 0:
                        structure = min(c.low for c in win)
                        stop = structure
                        if stop < bar.close:
                            self._reentry_armed = None
                            risk = bar.close - stop
                            return [Enter(
                                side=OrderSide.BUY, stop_loss=stop,
                                take_profit=bar.close + risk * self.reward,
                                comment=self.name, lots=self.fixed_lots)]
                    else:
                        structure = max(c.high for c in win)
                        stop = structure
                        if stop > bar.close:
                            self._reentry_armed = None
                            risk = stop - bar.close
                            return [Enter(
                                side=OrderSide.SELL, stop_loss=stop,
                                take_profit=bar.close - risk * self.reward,
                                comment=self.name, lots=self.fixed_lots)]

        # The chart decides the direction.
        votes = self.votes(candles)
        if not votes:
            return []
        buys = sum(1 for v in votes.values() if v > 0)
        sells = sum(1 for v in votes.values() if v < 0)

        if self.his_three:
            # HIS THREE CONFIRMATIONS, IN HIS ORDER AND HIS TAXONOMY.
            #
            #   "So, if price is TRENDING to the downside and we see SUPPORT here,
            #    there's only one more thing we need. We got two confirmations. Our
            #    THIRD CONFIRMATION IS A BREAK OF THAT SUPPORT."
            #
            # One per stage of his sequence -- trend, level, trigger -- not three
            # chart patterns agreeing with each other. min_votes=3 counted three
            # detectors from a pool of seven, which happens to be the same number
            # and is not the same thing at all. He never counts detectors.
            #
            # 1. TREND. He checks it first and everything else is downstream:
            #    "first off i need to determine are we going up are we going down."
            direction = self._higher_tf_gate(candles)
            if direction == 0:
                return []
            # 2. THE LEVEL. "we see support here" -- price has to actually be at
            #    one, from the same wick-clustered map his zones come from.
            levels = level_map(candles)
            if not levels:
                return []
            here = candles[-1]
            at = snap_to_level(here.close, levels, -direction)
            if at is None:
                return []
            near = here.close * 0.0006
            reached = (here.low <= at + near if direction > 0
                       else here.high >= at - near)
            if not reached:
                return []
            # 3. THE TRIGGER. "our third confirmation is a break of that support"
            #    -- one signal firing in the trend's direction, not a quorum.
            agreeing = buys if direction > 0 else sells
            if agreeing < 1:
                return []
        elif buys >= self.min_votes and buys > sells:
            direction = 1
        elif sells >= self.min_votes and sells > buys:
            direction = -1
        else:
            return []

        # His Bitcoin master switch. BTC publishes where it is going; the alts are
        # only allowed to follow. "anytime bitcoin falls or gets pumped most other
        # cryptos... are going to pump up as well."
        if self.btc_gates_alts:
            symbol = context.symbol.upper()
            is_btc = symbol.startswith("BTC")
            alt = symbol.endswith("USD") and symbol[:3] in (
                "ETH", "LTC", "XRP", "DOG", "SOL", "AVA", "LIN", "FIL",
            )
            if is_btc:
                type(self)._btc_bias = direction
                type(self)._btc_seen_at = context.now
            elif alt:
                fresh = (
                    type(self)._btc_seen_at is not None
                    and abs((context.now - type(self)._btc_seen_at).total_seconds())
                    <= 3600
                )
                # No recent read on Bitcoin means no opinion to follow, so no trade.
                # He never trades an alt without knowing what BTC is doing.
                if not fresh or type(self)._btc_bias != direction:
                    return []

        # The higher timeframes get the final say, because he checks them first.
        if self.higher_tf_gates and (self.h4_bars > 0 or self.daily_bars > 0):
            gate = self._higher_tf_gate(candles)
            if gate == 0 or gate != direction:
                return []

        bar = candles[-1]
        # HIS STOP IS THE TRIGGER CANDLE, not a swing window. "that last candle
        # where we broke, the high of that candle... That's where my stop loss is
        # going to go" -- and on his chart the stop sat exactly on that high, with
        # no pad. The old stop_bars=24 was mine.
        window = candles[-1:]
        # "stops are gonna be just below that moving average"
        ma_level = None
        if self.stop_at_ma:
            closes = [c.close for c in candles]
            slow = sma(closes, self.ma_slow)
            if slow and slow[-1] is not None:
                ma_level = slow[-1]

        if direction > 0:
            structure = min(c.low for c in window)
            if ma_level is not None and ma_level < bar.close:
                structure = max(structure, ma_level)
            stop = structure
            if stop >= bar.close:
                return []
            risk = bar.close - stop
            # "super, super tight stop losses"
            if self.max_stop_pct > 0 and risk > bar.close * self.max_stop_pct:
                if self.skip_if_stop_too_wide:
                    return []
                stop = bar.close - bar.close * self.max_stop_pct
                risk = bar.close - stop
            return [Enter(side=OrderSide.BUY, stop_loss=stop,
                          take_profit=bar.close + risk * self.reward,
                          comment=self.name, lots=self.fixed_lots)]

        structure = max(c.high for c in window)
        if ma_level is not None and ma_level > bar.close:
            structure = min(structure, ma_level)
        stop = structure
        if stop <= bar.close:
            return []
        risk = stop - bar.close
        if self.max_stop_pct > 0 and risk > bar.close * self.max_stop_pct:
            if self.skip_if_stop_too_wide:
                return []
            stop = bar.close + bar.close * self.max_stop_pct
            risk = stop - bar.close
        return [Enter(side=OrderSide.SELL, stop_loss=stop,
                      take_profit=bar.close - risk * self.reward,
                      comment=self.name, lots=self.fixed_lots)]
