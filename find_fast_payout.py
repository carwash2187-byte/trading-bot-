#!/usr/bin/env python3
"""Find a setting that unlocks payouts in 20 days instead of 43.

The gate is five separate days closing at +0.5% or better. At the current
setting 20% of all days qualify, which reaches five in about 43 days. Twenty
days needs 25% of days qualifying, so the search is for anything that raises
the *rate* of qualifying days without wrecking the edge that makes them.

Two levers move that rate and they are not equivalent:

* **Trading more often** raises the number of days that have any trade at all.
  Currently only a third of days do. This is the honest lever -- more chances,
  same quality per chance -- but loosening the entry too far buys extra trades
  by accepting worse ones, and the win rate falls.
* **Betting bigger** makes each winning day larger, so more of them clear the
  0.5% bar. This works immediately but it is also the dial that kills accounts,
  and past a point the profit falls while the drawdown keeps climbing.

So a candidate is only interesting if it unlocks fast, earns more, AND does not
raise the death rate. Anything that unlocks in 20 days by dying in 25 is worse
than useless -- the account has to survive to the payout to be paid.
"""

from __future__ import annotations

import itertools
import logging
import sys
from dataclasses import dataclass

from tradebot.backtest import run_backtest
from tradebot.data.history import bars
from tradebot.instruments import get_instrument
from tradebot.strategy.reversion import RsiScalper

logging.basicConfig(level=logging.WARNING)

GOLD = dict(spread_pct=0.000091, fee_pct=0.0000123)
INSTRUMENT = get_instrument("XAUUSD")
START = 10_000.0
DEATH = START * 0.94        # 6% below the starting balance, not the peak
TARGET_DAYS = 20


@dataclass
class Trial:
    timeframe: str
    oversold: float
    reward: float
    risk: float
    unlock_days: float = 0.0
    per_month: float = 0.0
    death_rate: float = 0.0
    win_rate: float = 0.0
    trades_per_week: float = 0.0
    runs: int = 0
    paid: int = 0

    @property
    def label(self) -> str:
        return (f"{self.timeframe} rsi{self.oversold:.0f} "
                f"r{self.reward} risk{self.risk:.1%}")

    @property
    def good(self) -> bool:
        """Fast payout, real money, and it survives to collect."""
        return (self.unlock_days <= TARGET_DAYS
                and self.per_month > 600
                and self.death_rate <= 0.20
                and self.paid >= self.runs * 0.7)


def qualifying_days(result) -> tuple[list, object]:
    """Days closing +0.5% on BALANCE, and the day the account died."""
    balance = {}
    running = START
    for trade in sorted(result.trades, key=lambda t: t["closed_at"]):
        running += trade["pnl"]
        balance[trade["closed_at"].date()] = running

    days = sorted(balance)
    previous = START
    qualifying = []
    for day in days:
        if previous and (balance[day] - previous) / previous >= 0.005:
            qualifying.append(day)
        previous = balance[day]

    died = None
    for stamp, equity in result.equity_curve:
        if equity <= DEATH:
            died = stamp.date()
            break
    return qualifying, died


def evaluate(trial: Trial, series, window_bars: int, step_bars: int) -> Trial:
    """Run this setting from many start dates and average what happened."""
    unlocks, months = [], []
    runs = died = paid = 0
    wins, trades, weeks = [], 0, 0.0

    start = 0
    while start + window_bars <= len(series):
        chunk = series[start:start + window_bars]
        runs += 1
        result = run_backtest(
            RsiScalper(oversold=trial.oversold,
                       overbought=100 - trial.oversold,
                       reward=trial.reward, trend_ema=200),
            chunk, symbol="XAUUSD", timeframe=trial.timeframe,
            instrument=INSTRUMENT, starting_balance=START,
            risk_per_trade=trial.risk, **GOLD,
        )
        months.append(result.per_week * 4.33)
        wins.append(result.win_rate)
        trades += len(result.trades)
        weeks += (chunk[-1].timestamp - chunk[0].timestamp).days / 7

        qualifying, dead = qualifying_days(result)
        if dead:
            died += 1
        if len(qualifying) >= 5:
            day = (qualifying[4] - chunk[0].timestamp.date()).days
            unlocks.append(day)
            if dead is None or qualifying[4] < dead:
                paid += 1
        start += step_bars

    trial.runs = runs
    trial.paid = paid
    trial.unlock_days = sum(unlocks) / len(unlocks) if unlocks else 999.0
    trial.per_month = sum(months) / len(months) if months else 0.0
    trial.death_rate = died / runs if runs else 0.0
    trial.win_rate = sum(wins) / len(wins) if wins else 0.0
    trial.trades_per_week = trades / weeks if weeks else 0.0
    return trial


def main() -> int:
    print("Searching for: payouts unlocked in 20 days, more money, no more deaths\n")

    series = {}
    for timeframe, days_per_bar in (("15m", 4 * 24), ("5m", 12 * 24)):
        try:
            series[timeframe] = (bars("PAXG-USD", timeframe), days_per_bar)
            print(f"  {timeframe}: {len(series[timeframe][0]):,} bars")
        except Exception as exc:                               # noqa: BLE001
            print(f"  {timeframe}: unavailable ({exc})")
    print()

    grid = list(itertools.product(
        sorted(series),                 # timeframe
        (35.0, 40.0, 45.0),             # entry threshold
        (1.0, 1.5, 2.0),                # reward multiple
        (0.015, 0.02, 0.03),            # risk per trade
    ))
    print(f"{len(grid)} settings to test\n")
    print(f"{'setting':<30} {'unlock':>7} {'$/month':>9} {'died':>6} "
          f"{'paid':>6} {'tr/wk':>6} {'win%':>6}")

    results = []
    for i, (timeframe, oversold, reward, risk) in enumerate(grid, 1):
        candles, bars_per_day = series[timeframe]
        # 90-day windows, stepped a month apart, so each setting is judged on
        # several different starting points rather than one lucky stretch.
        trial = evaluate(
            Trial(timeframe, oversold, reward, risk),
            candles, 90 * bars_per_day, 30 * bars_per_day,
        )
        results.append(trial)
        flag = "  <<< MEETS THE BRIEF" if trial.good else ""
        unlock = f"{trial.unlock_days:.0f}d" if trial.unlock_days < 999 else "never"
        print(f"{trial.label:<30} {unlock:>7} {trial.per_month:>9,.0f} "
              f"{trial.death_rate:>5.0%} {trial.paid:>3}/{trial.runs} "
              f"{trial.trades_per_week:>6.1f} {trial.win_rate:>6.1f}{flag}")
        sys.stdout.flush()

    print()
    winners = [t for t in results if t.good]
    if winners:
        winners.sort(key=lambda t: -t.per_month)
        print(f"{len(winners)} setting(s) meet the brief. Best:\n")
        for t in winners[:5]:
            print(f"  {t.label}")
            print(f"    unlocks in {t.unlock_days:.0f} days, "
                  f"${t.per_month:,.0f}/month, {t.death_rate:.0%} died, "
                  f"paid {t.paid}/{t.runs}")
    else:
        print("Nothing met all four conditions. Closest by unlock speed:\n")
        fast = sorted(results, key=lambda t: t.unlock_days)[:5]
        for t in fast:
            print(f"  {t.label}: unlock {t.unlock_days:.0f}d, "
                  f"${t.per_month:,.0f}/mo, {t.death_rate:.0%} died")
    return 0


if __name__ == "__main__":
    sys.exit(main())
