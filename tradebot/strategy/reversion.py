"""Strategies that are not trend-following.

Every strategy tested in this project so far buys strength and sells weakness.
BreakoutRider, KamaTrend and BigRunner differ in how they measure a trend, but
they are one idea wearing three hats, so their failures are correlated: they all
lost on the same choppy stretches for the same reason. Testing more of them
searches a narrower space than the count of experiments suggests.

These take the opposite side. A range-bound market punishes trend-following and
rewards fading extremes, and crypto spends most of its time range-bound. That
does not make these better -- it makes them wrong at different times, which is
the only property that lets a portfolio be steadier than its parts.

Every one of them carries the same known danger, so it is stated once here:
**mean reversion trades more often, and frequency is where fees kill.** An
earlier measurement in this project found an EMA cross earning $0.04 a trade
while paying $0.98 in fees -- an 87% win rate that arrived as a 27% loss. So
each strategy below demands a minimum move before acting, and none of them
trade a signal that is merely present rather than extreme.
"""

from __future__ import annotations

from ..brokers.base import OrderSide, Position
from ..data.indicators import atr, bollinger, ema, highest, lowest, rsi
from .base import Action, AdjustStop, Enter, Exit, Strategy, StrategyContext


class _Managed(Strategy):
    """Shared bookkeeping: own your positions, exit on a target or a stop."""

    def _mine(self, context: StrategyContext) -> list[Position]:
        return [p for p in context.open_positions if p.comment == self.name]

    def _exit_all(self, positions: list[Position], reason: str) -> list[Action]:
        return [Exit(ticket=p.ticket, reason=reason) for p in positions]


class MeanReverter(_Managed):
    """Buy panic, sell euphoria -- but only at a genuine extreme.

    Two conditions must agree, and they are deliberately different kinds of
    measurement: RSI says the move is exhausted relative to its own recent
    history, and the Bollinger band says it is far from the average in units of
    volatility. Either alone fires constantly in a trending market and gets run
    over; together they are rare.

    There is no trend filter on purpose. Adding one turns this back into a
    trend strategy, and the whole reason it exists is to be wrong at different
    times than those.
    """

    name = "mean_reverter"
    timeframe = "2h"
    lookback = 250

    def __init__(
        self,
        rsi_period: int = 14,
        oversold: float = 25.0,
        overbought: float = 75.0,
        band_period: int = 20,
        band_stdevs: float = 2.5,
        stop_atr: float = 2.0,
        atr_period: int = 14,
        allow_shorts: bool = True,
    ) -> None:
        self.rsi_period = rsi_period
        self.oversold = oversold
        self.overbought = overbought
        self.band_period = band_period
        self.band_stdevs = band_stdevs
        self.stop_atr = stop_atr
        self.atr_period = atr_period
        self.allow_shorts = allow_shorts

    def evaluate(self, context: StrategyContext) -> list[Action]:
        candles = context.candles
        if len(candles) < max(self.band_period, self.rsi_period, self.atr_period) + 5:
            return []

        bands = bollinger(candles, self.band_period, self.band_stdevs)
        strength = rsi(candles, self.rsi_period)
        atr_series = atr(candles, self.atr_period)

        close = candles[-1].close
        middle, upper, lower = bands.middle[-1], bands.upper[-1], bands.lower[-1]
        rsi_now, atr_now = strength[-1], atr_series[-1]
        if None in (middle, upper, lower, rsi_now, atr_now) or atr_now <= 0:
            return []

        mine = self._mine(context)
        if mine:
            # The target is the average, not the far band. Reversion is
            # reliable back to the middle and speculative past it.
            done = (
                close >= middle if mine[0].is_long else close <= middle
            )
            return self._exit_all(mine, "reverted") if done else []

        if context.has_position:
            return []
        if context.news is not None and context.news.active:
            return []

        if close < lower and rsi_now < self.oversold:
            return [Enter(side=OrderSide.BUY,
                          stop_loss=close - self.stop_atr * atr_now,
                          comment=self.name)]
        if self.allow_shorts and close > upper and rsi_now > self.overbought:
            return [Enter(side=OrderSide.SELL,
                          stop_loss=close + self.stop_atr * atr_now,
                          comment=self.name)]
        return []


class RsiScalper(_Managed):
    """Many small trades off an RSI extreme, with a fixed reward-to-risk exit.

    This is the shape of strategy that only works where trading is cheap, and
    on gold it is: a 100oz lot at $4,050 is $405,000 of notional, so
    AquaFunded's $5 commission is 0.0012%, and the quoted spread measured off
    Leo's own screen was 0.0091%. About 0.010% a round trip, against 0.104% on
    BTCUSD -- roughly a tenfold difference.

    That ratio is the entire argument for trading gold rather than crypto with
    something like this. An earlier measurement in this project found a fast
    strategy earning $0.04 a trade while paying $0.98 in fees; the edge per
    trade never changed, only the toll. Where the toll is a tenth as large, the
    same edge survives.

    Unlike :class:`MeanReverter` the exit is a fixed multiple of the stop
    distance rather than a return to the average, because a scalper needs to
    know its reward before it enters, not whenever the mean happens to arrive.
    """

    name = "rsi_scalper"
    timeframe = "15m"
    lookback = 200

    def __init__(
        self,
        rsi_period: int = 14,
        oversold: float = 30.0,
        overbought: float = 70.0,
        stop_atr: float = 1.0,
        reward: float = 1.5,
        trend_ema: int | None = 200,
        atr_period: int = 14,
        allow_shorts: bool = True,
    ) -> None:
        self.rsi_period = rsi_period
        self.oversold = oversold
        self.overbought = overbought
        self.stop_atr = stop_atr
        self.reward = reward
        self.trend_ema = trend_ema
        self.atr_period = atr_period
        self.allow_shorts = allow_shorts

    def evaluate(self, context: StrategyContext) -> list[Action]:
        candles = context.candles
        needed = max(self.rsi_period, self.atr_period, self.trend_ema or 0) + 5
        if len(candles) < needed:
            return []

        closes = [c.close for c in candles]
        strength = rsi(candles, self.rsi_period)
        atr_series = atr(candles, self.atr_period)
        rsi_now, atr_now, close = strength[-1], atr_series[-1], closes[-1]
        if rsi_now is None or atr_now is None or atr_now <= 0:
            return []

        # The bracket does the exiting. A scalper that manages its own exits
        # bar by bar cannot react between scheduled runs, and the whole trade
        # is often over inside one bar.
        if context.has_position:
            return []
        if context.news is not None and context.news.active:
            return []

        trend_now = None
        if self.trend_ema:
            trend_now = ema(closes, self.trend_ema)[-1]
            if trend_now is None:
                return []

        stop_distance = self.stop_atr * atr_now
        if rsi_now < self.oversold and (trend_now is None or close > trend_now):
            return [Enter(side=OrderSide.BUY,
                          stop_loss=close - stop_distance,
                          take_profit=close + self.reward * stop_distance,
                          comment=self.name)]
        if (self.allow_shorts and rsi_now > self.overbought
                and (trend_now is None or close < trend_now)):
            return [Enter(side=OrderSide.SELL,
                          stop_loss=close + stop_distance,
                          take_profit=close - self.reward * stop_distance,
                          comment=self.name)]
        return []


class PullbackBuyer(_Managed):
    """Buy a dip inside an uptrend, not a breakout.

    Trend-following buys the high; this waits for the same trend to go on sale.
    The difference matters at the stop: buying a breakout puts the stop far
    below, while buying a pullback puts it just under the support that was
    tested, so the same dollar risk buys a much larger position.

    Long only. This is a trend strategy in its entry filter, and shorts lost on
    every market tested in this project.
    """

    name = "pullback_buyer"
    timeframe = "2h"
    lookback = 300

    def __init__(
        self,
        trend_ema: int = 200,
        pullback_ema: int = 20,
        target_atr: float = 3.0,
        stop_atr: float = 1.5,
        atr_period: int = 14,
    ) -> None:
        self.trend_ema = trend_ema
        self.pullback_ema = pullback_ema
        self.target_atr = target_atr
        self.stop_atr = stop_atr
        self.atr_period = atr_period

    def evaluate(self, context: StrategyContext) -> list[Action]:
        candles = context.candles
        if len(candles) < self.trend_ema + 5:
            return []

        closes = [c.close for c in candles]
        trend = ema(closes, self.trend_ema)
        support = ema(closes, self.pullback_ema)
        atr_series = atr(candles, self.atr_period)

        close = closes[-1]
        trend_now, support_now, atr_now = trend[-1], support[-1], atr_series[-1]
        if None in (trend_now, support_now, atr_now) or atr_now <= 0:
            return []

        mine = self._mine(context)
        if mine:
            entry = mine[0].entry_price
            if close >= entry + self.target_atr * atr_now:
                return self._exit_all(mine, "target")
            if close < trend_now:
                return self._exit_all(mine, "trend-lost")
            return []

        if context.has_position:
            return []
        if context.news is not None and context.news.active:
            return []

        # The setup: a real uptrend, price dipped to the short average, and the
        # dip has stopped. Requiring the turn is what separates a pullback from
        # a collapse -- without it this buys every leg of a crash.
        uptrend = close > trend_now
        touched = min(c.low for c in candles[-3:]) <= support_now
        turning = close > candles[-2].close and candles[-2].close <= candles[-3].close

        if uptrend and touched and turning:
            return [Enter(side=OrderSide.BUY,
                          stop_loss=min(c.low for c in candles[-3:]) - self.stop_atr * atr_now,
                          comment=self.name)]
        return []


class RangeFader(_Managed):
    """Fade the edges of a range, and only while the market is actually ranging.

    The regime test is the whole strategy. Fading a breakout is how accounts
    die, so this refuses to trade unless recent range width is small relative
    to its own history -- that is, unless the market has been going nowhere.
    When volatility expands it stands aside and lets the trend strategies work.
    """

    name = "range_fader"
    timeframe = "2h"
    lookback = 300

    def __init__(
        self,
        channel: int = 40,
        quiet_ratio: float = 0.75,
        stop_atr: float = 1.5,
        atr_period: int = 14,
        allow_shorts: bool = True,
    ) -> None:
        self.channel = channel
        self.quiet_ratio = quiet_ratio
        self.stop_atr = stop_atr
        self.atr_period = atr_period
        self.allow_shorts = allow_shorts

    def evaluate(self, context: StrategyContext) -> list[Action]:
        candles = context.candles
        if len(candles) < self.channel * 3:
            return []

        highs = [c.high for c in candles]
        lows = [c.low for c in candles]
        atr_series = atr(candles, self.atr_period)

        tops = highest(highs, self.channel)
        bottoms = lowest(lows, self.channel)
        top, bottom = tops[-1], bottoms[-1]
        atr_now = atr_series[-1]
        if None in (top, bottom, atr_now) or atr_now <= 0 or top <= bottom:
            return []

        close = candles[-1].close
        middle = (top + bottom) / 2.0

        mine = self._mine(context)
        if mine:
            done = close >= middle if mine[0].is_long else close <= middle
            return self._exit_all(mine, "faded-to-middle") if done else []

        if context.has_position:
            return []
        if context.news is not None and context.news.active:
            return []

        # Is the market quiet? Compare this window's width to the widest recent
        # window. A range that is wide by its own standards is a trend.
        widths = [
            tops[i] - bottoms[i]
            for i in range(-self.channel * 2, 0)
            if tops[i] is not None and bottoms[i] is not None
        ]
        wide = max(widths) if widths else 0.0
        if wide <= 0 or (top - bottom) / wide > self.quiet_ratio:
            return []

        edge = (top - bottom) * 0.15
        if close <= bottom + edge:
            return [Enter(side=OrderSide.BUY,
                          stop_loss=bottom - self.stop_atr * atr_now,
                          comment=self.name)]
        if self.allow_shorts and close >= top - edge:
            return [Enter(side=OrderSide.SELL,
                          stop_loss=top + self.stop_atr * atr_now,
                          comment=self.name)]
        return []
