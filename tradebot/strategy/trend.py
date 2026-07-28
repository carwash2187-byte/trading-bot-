"""Concrete trend strategies.

Every rule here traces back to a measured result rather than a preference, and
the ones that cost money are recorded as comments so they do not get
reintroduced later:

* **Long only.** Short trades lost money on every market tested (gold, BTC,
  ETH, SOL). Dropping them raised BTC from +157% to +165% *and* cut the worst
  drawdown from 31% to 17%.
* **Two-hour bars.** 30-minute and 1-hour both die on commission: BTC 1h paid
  $5,253 in fees on a $10k account to lose 2.3%. 4h trades too rarely.
* **Bank part of the winner.** Taking 30% off at a profit target lifted the win
  rate from 36.6% to 54.8% and improved five of six markets.

None of that makes these profitable *now* -- the same tests showed the edge
decaying year over year, which is the entire reason the portfolio manager
exists. These are candidates for the stack, not answers.
"""

from __future__ import annotations

from ..brokers.base import OrderSide
from ..data.indicators import atr, ema, highest, kama, williams_r
from .base import Action, AdjustStop, Enter, Exit, Strategy, StrategyContext


class _LongTrendBase(Strategy):
    """Shared position management for long-only trend following.

    The scale-out and trailing logic is deliberately *stateless*: it reads the
    broker's own stop to decide what has already happened. A scheduled bot
    exits between cycles, so anything held in memory is gone by the next run,
    and a separate state file would be one more thing to corrupt or desync.

    The trick is that banking profit also moves the stop to breakeven, so
    ``stop >= entry`` is itself the record that the bank already happened.
    """

    bank_at_atr: float = 3.0        # profit target for the partial exit
    bank_fraction: float = 0.30     # how much of the position to take off
    trail_atr: float = 2.0          # trail distance once the bank is done
    stop_atr: float = 4.0           # initial stop distance

    def _manage(self, context: StrategyContext, atr_now: float) -> list[Action]:
        actions: list[Action] = []
        for position in context.open_positions:
            if not position.is_long:
                continue

            banked = (
                position.stop_loss is not None
                and position.stop_loss >= position.entry_price
            )
            profit = context.bid - position.entry_price

            if not banked:
                if profit >= self.bank_at_atr * atr_now:
                    keep = round(position.lots * self.bank_fraction, 4)
                    if keep > 0:
                        actions.append(
                            Exit(ticket=position.ticket, lots=keep, reason="bank-partial")
                        )
                    # Breakeven both protects the rest and records the bank.
                    actions.append(
                        AdjustStop(ticket=position.ticket, stop_loss=position.entry_price)
                    )
                continue

            # Already banked: ratchet the stop up behind price, never down.
            candidate = context.bid - self.trail_atr * atr_now
            if position.stop_loss is None or candidate > position.stop_loss:
                actions.append(
                    AdjustStop(ticket=position.ticket, stop_loss=candidate)
                )
        return actions


class BreakoutRider(_LongTrendBase):
    """Buy a breakout in an uptrend, bank 30%, ride the rest with a trail.

    Entry needs two things to agree: price makes a new high over the breakout
    window, *and* sits above the long trend average. The trend filter is what
    stops this buying every spike in a downtrend.
    """

    name = "breakout_rider"
    timeframe = "2h"
    lookback = 300

    def __init__(
        self,
        breakout: int = 20,
        trend_ema: int = 200,
        exit_ema: int = 50,
        atr_period: int = 14,
    ) -> None:
        self.breakout = breakout
        self.trend_ema = trend_ema
        self.exit_ema = exit_ema
        self.atr_period = atr_period

    def evaluate(self, context: StrategyContext) -> list[Action]:
        candles = context.candles
        if len(candles) < max(self.trend_ema, self.breakout) + 2:
            return []

        closes = [c.close for c in candles]
        highs = [c.high for c in candles]

        atr_series = atr(candles, self.atr_period)
        trend = ema(closes, self.trend_ema)
        exit_line = ema(closes, self.exit_ema)
        # Compare against the window *ending on the previous bar*, otherwise the
        # current bar's own high is in the max and nothing can ever break out.
        prior_high = highest(highs, self.breakout)[-2]

        atr_now = atr_series[-1]
        trend_now = trend[-1]
        exit_now = exit_line[-1]
        close = closes[-1]
        if None in (atr_now, trend_now, exit_now, prior_high) or atr_now <= 0:
            return []

        actions = self._manage(context, atr_now)

        if context.has_position:
            if close < exit_now:
                actions = [
                    Exit(ticket=p.ticket, reason="trend-exit")
                    for p in context.open_positions
                ]
            return actions

        # Stand aside inside a news window. Entries there get the worst spread
        # and the least predictable fill of the whole session.
        if context.news is not None and context.news.active:
            return actions

        if close > prior_high and close > trend_now:
            actions.append(
                Enter(
                    side=OrderSide.BUY,
                    stop_loss=close - self.stop_atr * atr_now,
                    comment=self.name,
                )
            )
        return actions


class KamaTrend(_LongTrendBase):
    """Kaufman adaptive trend follower with a range filter.

    Modelled on the only published strategy of three that survived an honest
    re-test once fees were charged. Its author sized risk at 2% and reported
    16% a year over 2014-2023 -- a real number, and a useful reminder of the
    scale that actually holds up.

    The Williams %R filter demands a *recent pullback* before the breakout is
    taken. A first pass refused entries while price sat at the top of its
    range, which sounds prudent and is in fact self-defeating: a breakout is by
    definition a new high, so that rule could never fire. Requiring a dip in
    the preceding few bars keeps the intent -- don't buy the fifth vertical bar
    of a run -- without contradicting the entry itself.
    """

    name = "kama_trend"
    timeframe = "2h"
    lookback = 300

    stop_atr: float = 5.0           # the author's wider stop, kept as published
    trail_atr: float = 3.0

    def __init__(
        self,
        kama_period: int = 10,
        rising_bars: int = 10,
        breakout: int = 30,
        wpr_period: int = 20,
        pullback_level: float = -50.0,
        # Wider than the rising-bars window on purpose. The dip has to sit
        # *behind* the run-up it precedes, so a window short enough to overlap
        # it would again be asking for two things that cannot both be true.
        pullback_bars: int = 25,
        atr_period: int = 14,
    ) -> None:
        self.kama_period = kama_period
        self.rising_bars = rising_bars
        self.breakout = breakout
        self.wpr_period = wpr_period
        self.pullback_level = pullback_level
        self.pullback_bars = pullback_bars
        self.atr_period = atr_period

    def evaluate(self, context: StrategyContext) -> list[Action]:
        candles = context.candles
        needed = self.kama_period + self.rising_bars + self.breakout + 5
        if len(candles) < needed:
            return []

        closes = [c.close for c in candles]
        line = kama(closes, self.kama_period)
        atr_series = atr(candles, self.atr_period)
        wpr = williams_r(candles, self.wpr_period)
        prior_high = highest(closes, self.breakout)[-2]

        atr_now = atr_series[-1]
        close = closes[-1]
        if atr_now is None or atr_now <= 0 or prior_high is None:
            return []

        recent = line[-(self.rising_bars + 1) :]
        if any(v is None for v in recent):
            return []
        rising = all(recent[i] > recent[i - 1] for i in range(1, len(recent)))

        actions = self._manage(context, atr_now)

        if context.has_position:
            # Exit when the adaptive line rolls over -- the author's own signal.
            if len(recent) >= 2 and recent[-1] < recent[-2]:
                actions = [
                    Exit(ticket=p.ticket, reason="kama-turn")
                    for p in context.open_positions
                ]
            return actions

        # Stand aside inside a news window. Entries there get the worst spread
        # and the least predictable fill of the whole session.
        if context.news is not None and context.news.active:
            return actions

        # Look at the bars *before* this one: was there a dip into the lower
        # half of the range to break out of? Excluding the current bar matters,
        # since the breakout bar itself is always pinned to the top.
        prior_wpr = wpr[-(self.pullback_bars + 1) : -1]
        pulled_back = any(
            v is not None and v <= self.pullback_level for v in prior_wpr
        )
        if not pulled_back:
            return actions

        if rising and close > prior_high:
            actions.append(
                Enter(
                    side=OrderSide.BUY,
                    stop_loss=close - self.stop_atr * atr_now,
                    comment=self.name,
                )
            )
        return actions
