"""The Big-Runner — the one strategy that survived out-of-sample testing.

Roughly 239 backtests were run across gold, BTC, ETH, SOL and forex. Almost all
of them died the moment they were shown a stretch of history they had not been
fitted on. This one was tested out-of-sample twice and held up both times, which
is the only reason it is here rather than in the graveyard with the rest.

Three rules have to agree before it will enter:

* **Supertrend has just flipped.** Not "is in a trend" -- the bar it *turns*.
  Entering mid-trend was measurably worse; by then most of the move is gone.
* **Price is the right side of the 100-bar average.** This is the regime
  filter, and it is what stops the flip signal from buying every bounce inside
  a downtrend.
* **MACD agrees.** A third opinion from a different kind of measurement, which
  is the point -- two flavours of the same trend measure would just be the same
  vote counted twice.

The exits are where the name comes from, and they are deliberately lopsided:

* **Initial stop 1.5 ATR.** Tight. A trade that was wrong is wrong quickly, and
  paying little to find that out is most of the edge.
* **Trail 8 ATR.** Loose, and it only ever ratchets one way. Once a trade is
  working it is given enough room to survive an ordinary pullback, because the
  whole return comes from the handful of trades that run a long way. A tighter
  trail raised the win rate and lost money -- it kept clipping the winners that
  paid for everything else.

Unlike the strategies in ``trend.py`` this one takes shorts. Those were dropped
there because they lost on every market tested; here they were part of what was
validated, so removing them would leave a strategy nobody has actually measured.
"""

from __future__ import annotations

from ..brokers.base import OrderSide, Position
from ..data.indicators import atr, ema, macd, supertrend
from .base import Action, AdjustStop, Enter, Exit, Strategy, StrategyContext


class BigRunner(Strategy):
    """Trade the turn, cut it fast if wrong, and give it room if it works."""

    name = "big_runner"
    timeframe = "2h"
    lookback = 400

    def __init__(
        self,
        st_factor: float = 1.5,
        st_period: int = 14,
        regime_ema: int = 100,
        macd_fast: int = 12,
        macd_slow: int = 26,
        macd_signal: int = 9,
        stop_atr: float = 1.5,
        trail_atr: float = 8.0,
        atr_period: int = 14,
    ) -> None:
        self.st_factor = st_factor
        self.st_period = st_period
        self.regime_ema = regime_ema
        self.macd_fast = macd_fast
        self.macd_slow = macd_slow
        self.macd_signal = macd_signal
        self.stop_atr = stop_atr
        self.trail_atr = trail_atr
        self.atr_period = atr_period

    # -- position management ---------------------------------------------

    def _trail(self, context: StrategyContext, atr_now: float) -> list[Action]:
        """Ratchet the stop toward price, never away from it.

        Reading the broker's existing stop rather than remembering our own is
        what lets this survive the process exiting between scheduled runs --
        there is no in-memory trail state to lose and no state file to desync.
        """
        actions: list[Action] = []
        for position in context.open_positions:
            if position.comment != self.name:
                continue

            if position.is_long:
                candidate = context.bid - self.trail_atr * atr_now
                improved = position.stop_loss is None or candidate > position.stop_loss
            else:
                candidate = context.ask + self.trail_atr * atr_now
                improved = position.stop_loss is None or candidate < position.stop_loss

            if improved:
                actions.append(
                    AdjustStop(ticket=position.ticket, stop_loss=candidate)
                )
        return actions

    def _mine(self, context: StrategyContext) -> list[Position]:
        return [p for p in context.open_positions if p.comment == self.name]

    # -- signals ----------------------------------------------------------

    def evaluate(self, context: StrategyContext) -> list[Action]:
        candles = context.candles
        needed = max(self.regime_ema, self.macd_slow + self.macd_signal, self.st_period)
        if len(candles) < needed + 2:
            return []

        closes = [c.close for c in candles]
        st = supertrend(candles, self.st_factor, self.st_period)
        lines = macd(candles, self.macd_fast, self.macd_slow, self.macd_signal)
        regime = ema(closes, self.regime_ema)
        atr_series = atr(candles, self.atr_period)

        atr_now = atr_series[-1]
        regime_now = regime[-1]
        macd_now = lines.macd[-1]
        signal_now = lines.signal[-1]
        close = closes[-1]
        if None in (atr_now, regime_now, macd_now, signal_now) or atr_now <= 0:
            return []

        actions = self._trail(context, atr_now)

        # An open position of ours means the trailing stop is the exit plan.
        # Second-guessing it here would defeat the point of a wide trail.
        mine = self._mine(context)
        if mine:
            # A flip against an open trade is the one signal worth acting on
            # early: the reason for being in the trade has gone.
            against = (
                st.flipped_down() if mine[0].is_long else st.flipped_up()
            )
            if against:
                return [
                    Exit(ticket=p.ticket, reason="supertrend-flip")
                    for p in mine
                ]
            return actions

        if context.has_position:
            # Someone else's position. Not ours to manage or to double up on.
            return actions

        if context.news is not None and context.news.active:
            return actions

        if st.flipped_up() and close > regime_now and macd_now > signal_now:
            actions.append(
                Enter(
                    side=OrderSide.BUY,
                    stop_loss=close - self.stop_atr * atr_now,
                    comment=self.name,
                )
            )
        elif st.flipped_down() and close < regime_now and macd_now < signal_now:
            actions.append(
                Enter(
                    side=OrderSide.SELL,
                    stop_loss=close + self.stop_atr * atr_now,
                    comment=self.name,
                )
            )
        return actions
