#!/usr/bin/env python3
"""Leo's challenge: looser triggers, more risk, and liquidity sweeps -- tested.

The bot sat out a $45 gold session yesterday, blocked once by the trend filter
and once by an RSI peak one point under the short trigger. The standing answer
has been "the pickiness IS the edge", but that is a claim, and claims about
settings are exactly what walk-forward testing is for. So: every loosening Leo
asked for, plus a real liquidity-sweep entry, judged on the same four unseen
stretches as everything else, on his actual balance, with deaths counted.

Deal attached to this file: whatever wins here gets deployed. The test is not
a way of saying no; it is how the decision gets made.
"""

from __future__ import annotations

import logging
import sys

from tradebot.backtest import run_backtest
from tradebot.brokers.base import OrderSide
from tradebot.data.history import bars
from tradebot.data.indicators import atr, ema, lowest, rsi
from tradebot.instruments import get_instrument
from tradebot.strategy.base import Enter, Strategy
from tradebot.strategy.reversion import RsiScalper

logging.basicConfig(level=logging.WARNING)

GOLD = dict(spread_pct=0.000102, fee_pct=0.0000123)
INSTRUMENT = get_instrument("XAUUSD")
BALANCE = 2_635.39
DEATH = BALANCE * 0.94


class SweepBuyer(Strategy):
    """Leo's liquidity-sweep idea, implemented straight.

    The pattern: price stabs below a recent low -- running the stops resting
    there -- and closes back above it. The reading is that the sellers were
    a hunt, not a trend, and the snap-back is tradable. Entry on the close
    that reclaims the swept low; stop under the wick that did the sweeping;
    the usual fixed reward multiple.
    """

    name = "sweep_buyer"
    timeframe = "15m"
    lookback = 60

    def __init__(self, window: int = 20, reward: float = 1.5,
                 allow_shorts: bool = True) -> None:
        self.window = window
        self.reward = reward
        self.allow_shorts = allow_shorts

    def evaluate(self, context):
        candles = context.candles
        if len(candles) < self.window + 3:
            return []
        if context.has_position:
            return []
        if context.news is not None and context.news.active:
            return []

        prior_low = min(c.low for c in candles[-self.window - 1:-1])
        prior_high = max(c.high for c in candles[-self.window - 1:-1])
        bar = candles[-1]

        # Swept the lows and closed back above them.
        if bar.low < prior_low and bar.close > prior_low:
            stop = bar.low - (bar.close - bar.low) * 0.1
            risk = bar.close - stop
            if risk > 0:
                return [Enter(side=OrderSide.BUY, stop_loss=stop,
                              take_profit=bar.close + self.reward * risk,
                              comment=self.name)]

        # Mirror image: swept the highs and closed back under.
        if self.allow_shorts and bar.high > prior_high and bar.close < prior_high:
            stop = bar.high + (bar.high - bar.close) * 0.1
            risk = stop - bar.close
            if risk > 0:
                return [Enter(side=OrderSide.SELL, stop_loss=stop,
                              take_profit=bar.close - self.reward * risk,
                              comment=self.name)]
        return []


class LooseShortScalper(RsiScalper):
    """The exact trade the bot missed: shorts without the trend filter."""

    name = "loose_short"

    def evaluate(self, context):
        # Longs keep the trend filter; shorts drop it. Implemented by asking
        # the parent twice with different settings rather than copying logic.
        with_filter = RsiScalper(oversold=self.oversold,
                                 overbought=self.overbought,
                                 reward=self.reward, trend_ema=self.trend_ema,
                                 allow_shorts=False)
        with_filter.lookback = self.lookback
        longs = with_filter.evaluate(context)
        if longs:
            return longs

        no_filter = RsiScalper(oversold=0.0,           # longs impossible
                               overbought=self.overbought,
                               reward=self.reward, trend_ema=None)
        no_filter.lookback = self.lookback
        return no_filter.evaluate(context)


CANDIDATES = {
    "champion (now live)": lambda: RsiScalper(
        oversold=35, overbought=65, reward=1.5, trend_ema=200),
    "shorts at 60": lambda: RsiScalper(
        oversold=35, overbought=60, reward=1.5, trend_ema=200),
    "shorts at 63": lambda: RsiScalper(
        oversold=35, overbought=63, reward=1.5, trend_ema=200),
    "no trend filter": lambda: RsiScalper(
        oversold=35, overbought=65, reward=1.5, trend_ema=None),
    "loose shorts only": lambda: LooseShortScalper(
        oversold=35, overbought=65, reward=1.5, trend_ema=200),
    "liquidity sweeps": lambda: SweepBuyer(window=20, reward=1.5),
    "sweeps, 2R": lambda: SweepBuyer(window=20, reward=2.0),
}


def main() -> int:
    candles = bars("PAXG-USD", "15m")
    quarter = len(candles) // 4
    print(f"{len(candles)} bars of gold, four unseen stretches, "
          f"${BALANCE:,.2f} account, death at ${DEATH:,.2f}\n")

    for risk in (0.015, 0.02):
        print(f"===== risk {risk:.1%} per trade =====")
        print(f"{'candidate':<22} {'$/month':>8} {'PF':>6} {'win%':>6} "
              f"{'trades':>7} {'stretches+':>10} {'died':>5}")
        for label, factory in CANDIDATES.items():
            months, wins, trades, positive, died = [], [], 0, 0, 0
            for k in range(4):
                chunk = candles[k * quarter:(k + 1) * quarter]
                result = run_backtest(
                    factory(), chunk, symbol="XAUUSD", timeframe="15m",
                    instrument=INSTRUMENT, starting_balance=BALANCE,
                    risk_per_trade=risk, **GOLD)
                months.append(result.per_week * 4.33)
                wins.append(result.win_rate)
                trades += len(result.trades)
                if result.net_profit > 0:
                    positive += 1
                if min(eq for _, eq in result.equity_curve) <= DEATH:
                    died += 1
            print(f"{label:<22} {sum(months)/4:>8,.0f} "
                  f"{'-':>6} {sum(wins)/4:>6.1f} {trades:>7} "
                  f"{positive:>8}/4 {died:>4}/4")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
