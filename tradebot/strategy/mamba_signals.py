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

from ..brokers.base import Candle, OrderSide
from ..data.indicators import ema
from .base import Action, AdjustStop, Enter, Exit, Strategy, StrategyContext
from .mamba import SESSION_OPENS_UTC
from .mamba_patterns import (
    double_top_bottom,
    engulfing,
    fair_value_gap,
    liquidity_sweep,
    macd_divergence,
)


class MambaSignals(Strategy):
    """Every pattern votes on direction; trade when enough of them agree.

    Args:
        min_votes: How many patterns must point the same way. Two is the
            "confluence" he talks about constantly -- "that's two confirmations
            if not like six".
        session: "you only trade during New York session". Empty string trades
            around the clock, which is what he does on gold and crypto.
        window_minutes: 210. "I don't like to trade much past 10:00 a.m."
        reward: 3.0. "a nice little one to three."
        max_hold_minutes: 35. "30 minutes, 35 minutes at the most."
        stop_bars: Bars whose extreme the stop sits behind. "stops are right above
            the highs."
        use_ma: Whether the moving averages get a vote. He mentions them beside
            the engulfing candle -- "our moving averages are above everything...
            gonna pull our trade to the downside".
        max_trades_per_day: 3.
        max_losses_per_day: 2.
        breakeven_at: R at which the stop goes to entry, after banking half.
        scale_at: R at which half comes off.
    """

    name = "mamba_signals"
    timeframe = "5m"
    lookback = 400

    def __init__(
        self,
        min_votes: int = 2,
        session: str = "newyork",
        sessions: tuple[str, ...] = (),
        window_minutes: int = 210,
        wait_for_close: bool = True,
        reward: float = 3.0,
        max_hold_minutes: int = 35,
        stop_bars: int = 24,
        zone_pct: float = 0.0004,
        use_ma: bool = True,
        ma_fast: int = 9,
        ma_slow: int = 21,
        h4_bars: int = 0,
        daily_bars: int = 0,
        higher_tf_gates: bool = True,
        max_trades_per_day: int = 3,
        max_losses_per_day: int = 2,
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
        self.stop_bars = stop_bars
        self.zone_pct = zone_pct
        self.use_ma = use_ma
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
        self.h4_bars = h4_bars
        self.daily_bars = daily_bars
        # His ORDER matters, not just his ingredients. "first off i need to
        # determine are we going up are we going down... and that's going to be
        # from the daily and the four hour." Direction is decided FIRST, by the
        # higher timeframes, and the patterns then confirm inside it. Treating
        # them as equal votes alongside the patterns is a different strategy and
        # a worse one -- it dilutes five pattern votes with two trend votes.
        self.higher_tf_gates = higher_tf_gates
        self.max_trades_per_day = max_trades_per_day
        self.max_losses_per_day = max_losses_per_day
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

        # "lower lows higher high on our macd... price is bound to reverse"
        div = macd_divergence(candles)
        if div:
            out["macd"] = div

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

        # "our moving averages are above everything... gonna pull our trade to
        # the downside"
        if self.use_ma:
            closes = [c.close for c in candles]
            fast = ema(closes, self.ma_fast)
            slow = ema(closes, self.ma_slow)
            if fast and slow and fast[-1] is not None and slow[-1] is not None:
                out["ma"] = 1 if fast[-1] > slow[-1] else -1

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

        # Managing what is open comes before any entry gate, always.
        if self.max_hold_minutes > 0:
            for pos in context.open_positions:
                if pos.comment != self.name:
                    continue
                held = (context.now - pos.opened_at).total_seconds() / 60
                if held >= self.max_hold_minutes:
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
        if (self.max_losses_per_day > 0
                and context.risk.losses_today(self.name) >= self.max_losses_per_day):
            return []
        if context.news is not None and context.news.active:
            return []
        if not self._in_session(context.now):
            return []

        # The chart decides the direction.
        votes = self.votes(candles)
        if not votes:
            return []
        buys = sum(1 for v in votes.values() if v > 0)
        sells = sum(1 for v in votes.values() if v < 0)

        if buys >= self.min_votes and buys > sells:
            direction = 1
        elif sells >= self.min_votes and sells > buys:
            direction = -1
        else:
            return []

        # The higher timeframes get the final say, because he checks them first.
        if self.higher_tf_gates and (self.h4_bars > 0 or self.daily_bars > 0):
            gate = self._higher_tf_gate(candles)
            if gate == 0 or gate != direction:
                return []

        bar = candles[-1]
        window = candles[-self.stop_bars:]
        # "stops are right above the highs" / "below the low right here to the left"
        # "stops are gonna be just below that moving average"
        ma_level = None
        if self.stop_at_ma:
            closes = [c.close for c in candles]
            slow = ema(closes, self.ma_slow)
            if slow and slow[-1] is not None:
                ma_level = slow[-1]

        if direction > 0:
            structure = min(c.low for c in window)
            if ma_level is not None and ma_level < bar.close:
                structure = max(structure, ma_level)
            stop = structure - structure * self.zone_pct
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
        stop = structure + structure * self.zone_pct
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
