#!/usr/bin/env python3
"""Search for a strategy configuration worth trading.

Backtests are free and local now, so the constraint is no longer how many can
be run -- it is not fooling yourself with the results. Two guards do most of
that work here:

**Every candidate is scored on unseen data.** The window is split in two: the
search only ever sees the first part, and the winner is then run once on the
second. Almost everything that looks good in-sample dies at that step, which is
the entire point of taking it.

**A candidate must clear a floor before it counts.** Enough trades to not be
luck, and a profit factor with a margin above break-even, because 1.02 over
forty trades is noise wearing a suit.
"""

from __future__ import annotations

import argparse
import itertools
import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from tradebot.backtest import run_backtest
from tradebot.data.history import bars
from tradebot.strategy.reversion import MeanReverter, PullbackBuyer, RangeFader
from tradebot.strategy.runner import BigRunner
from tradebot.strategy.trend import BreakoutRider, KamaTrend

log = logging.getLogger("sweep")

# Cost profiles for the two venues Leo can actually reach. Crypto on
# AquaFunded pays no commission but a wide quoted spread; Bybit is the
# opposite. Testing at zero cost would just reproduce the mistake that made
# every leaderboard strategy look good.
VENUES = {
    "aqua": dict(spread_pct=0.00104, fee_pct=0.0),
    "bybit": dict(spread_pct=0.0001, fee_pct=0.00055),
}

SYMBOLS = {
    "BTC-USD": "BTCUSD", "ETH-USD": "ETHUSD", "SOL-USD": "SOLUSD",
    "XRP-USD": "XRPUSD", "DOGE-USD": "DOGEUSD", "LINK-USD": "LINKUSD",
    "AVAX-USD": "AVAXUSD", "LTC-USD": "LTCUSD",
}


@dataclass
class Candidate:
    """One configuration and how it did."""

    label: str
    product: str
    timeframe: str
    risk: float
    factory: object
    result: object = None

    @property
    def score(self) -> float:
        """Rank by profit per unit of pain, not by profit.

        Ranking on raw return picks whichever setting took the most risk, which
        is how a search talks itself into a strategy that cannot be traded.
        """
        r = self.result
        if r is None or not r.trades:
            return -1e9
        drawdown = max(r.max_drawdown_pct, 1.0)
        return r.per_week / drawdown


def instrument_for(symbol: str, price: float):
    """A sane contract spec for a coin the catalog does not know.

    Lot sizing has to work for a $0.15 coin and a $70,000 one, so the contract
    size is scaled to the price rather than fixed at 1.
    """
    from tradebot.instruments import Instrument

    size = 1.0
    while price * size < 1_000:
        size *= 10.0
    return Instrument(
        symbol=symbol, contract_size=size, tick_size=0.0001,
        min_lot=0.001, max_lot=1_000.0, lot_step=0.001,
        base_currency=symbol[:-3], quote_currency="USD", digits=4,
    )


def evaluate(candidate: Candidate, candles, venue: str, balance: float):
    symbol = SYMBOLS[candidate.product]
    candidate.result = run_backtest(
        candidate.factory(),
        candles,
        symbol=symbol,
        timeframe=candidate.timeframe,
        starting_balance=balance,
        risk_per_trade=candidate.risk,
        instrument=instrument_for(symbol, candles[len(candles) // 2].close),
        **VENUES[venue],
    )
    return candidate


def build_candidates(products, timeframes, risks) -> list[Candidate]:
    """The grid. Parameters vary around what previous testing pointed at."""
    out = []
    for product, tf, risk in itertools.product(products, timeframes, risks):
        for trail in (4.0, 8.0, 12.0):
            for stop in (1.5, 3.0):
                out.append(Candidate(
                    label=f"big_runner st{stop} tr{trail}",
                    product=product, timeframe=tf, risk=risk,
                    factory=lambda s=stop, t=trail: BigRunner(stop_atr=s, trail_atr=t),
                ))
        for breakout in (20, 55):
            out.append(Candidate(
                label=f"breakout_rider n{breakout}",
                product=product, timeframe=tf, risk=risk,
                factory=lambda b=breakout: BreakoutRider(breakout=b),
            ))
        out.append(Candidate(
            label="kama_trend", product=product, timeframe=tf, risk=risk,
            factory=KamaTrend,
        ))
        # The non-trend family. These lose on BTC 2h; included because losing
        # there says nothing about whether they work on a different market,
        # and a strategy that is wrong at different times is what a portfolio
        # actually needs.
        for oversold in (20.0, 30.0):
            out.append(Candidate(
                label=f"mean_reverter rsi{oversold:.0f}",
                product=product, timeframe=tf, risk=risk,
                factory=lambda o=oversold: MeanReverter(
                    oversold=o, overbought=100.0 - o),
            ))
        for target in (2.0, 4.0):
            out.append(Candidate(
                label=f"pullback_buyer t{target:.0f}",
                product=product, timeframe=tf, risk=risk,
                factory=lambda t=target: PullbackBuyer(target_atr=t),
            ))
        out.append(Candidate(
            label="range_fader", product=product, timeframe=tf, risk=risk,
            factory=RangeFader,
        ))
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--venue", choices=sorted(VENUES), default="aqua")
    parser.add_argument("--balance", type=float, default=20_000.0)
    parser.add_argument("--symbols", nargs="+", default=["BTC-USD", "ETH-USD", "SOL-USD"])
    parser.add_argument("--timeframes", nargs="+", default=["2h", "4h"])
    parser.add_argument("--risks", nargs="+", type=float, default=[0.01, 0.02])
    parser.add_argument("--start", default="2023-07-01")
    parser.add_argument("--end", default="2026-07-20")
    parser.add_argument("--min-trades", type=int, default=30)
    parser.add_argument("--min-pf", type=float, default=1.15)
    parser.add_argument("--top", type=int, default=15)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(message)s",
    )

    start = datetime.fromisoformat(args.start).replace(tzinfo=timezone.utc)
    end = datetime.fromisoformat(args.end).replace(tzinfo=timezone.utc)

    series: dict[tuple[str, str], list] = {}
    for product in args.symbols:
        for tf in args.timeframes:
            try:
                series[(product, tf)] = bars(product, tf, start, end)
            except Exception as exc:                       # noqa: BLE001
                print(f"  skipping {product} {tf}: {exc}")

    candidates = [
        c for c in build_candidates(args.symbols, args.timeframes, args.risks)
        if (c.product, c.timeframe) in series
    ]
    print(f"{len(candidates)} configurations, venue={args.venue}, "
          f"${args.balance:,.0f}\n")

    # The split. Everything before the line is used to search; everything after
    # is untouched until a winner has already been chosen.
    scored = []
    for i, candidate in enumerate(candidates, 1):
        candles = series[(candidate.product, candidate.timeframe)]
        cut = int(len(candles) * 0.6)
        try:
            evaluate(candidate, candles[:cut], args.venue, args.balance)
        except Exception as exc:                           # noqa: BLE001
            log.info("  %s failed: %s", candidate.label, exc)
            continue
        scored.append(candidate)
        if i % 20 == 0:
            print(f"  ...{i}/{len(candidates)}")

    survivors = [
        c for c in scored
        if c.result and len(c.result.trades) >= args.min_trades
        and c.result.profit_factor >= args.min_pf
    ]
    survivors.sort(key=lambda c: c.score, reverse=True)

    print(f"\n{len(survivors)} of {len(scored)} cleared the floor "
          f"({args.min_trades}+ trades, PF {args.min_pf}+)\n")
    print(f"{'IN-SAMPLE':<34} {'$/wk':>8} {'PF':>6} {'win%':>6} {'DD%':>6} {'n':>5}")
    for c in survivors[: args.top]:
        r = c.result
        print(f"{c.label[:20]:<20} {c.product[:8]:<9} {c.timeframe:<4} "
              f"{r.per_week:>8,.0f} {r.profit_factor:>6.2f} "
              f"{r.win_rate:>6.1f} {r.max_drawdown_pct:>6.1f} {len(r.trades):>5}")

    if not survivors:
        print("nothing cleared the floor -- no candidate worth testing further")
        return

    # The decisive step. Anything that dies here was curve-fitting.
    print(f"\n{'OUT-OF-SAMPLE (unseen data)':<34} {'$/wk':>8} {'PF':>6} "
          f"{'win%':>6} {'DD%':>6} {'n':>5}")
    held_up = []
    for c in survivors[: args.top]:
        candles = series[(c.product, c.timeframe)]
        cut = int(len(candles) * 0.6)
        fresh = Candidate(c.label, c.product, c.timeframe, c.risk, c.factory)
        try:
            evaluate(fresh, candles[cut:], args.venue, args.balance)
        except Exception:                                  # noqa: BLE001
            continue
        r = fresh.result
        alive = r.profit_factor >= 1.0 and r.net_profit > 0
        held_up.append(fresh) if alive else None
        print(f"{c.label[:20]:<20} {c.product[:8]:<9} {c.timeframe:<4} "
              f"{r.per_week:>8,.0f} {r.profit_factor:>6.2f} "
              f"{r.win_rate:>6.1f} {r.max_drawdown_pct:>6.1f} {len(r.trades):>5}"
              f"  {'HELD UP' if alive else 'died'}")

    print(f"\n{len(held_up)} of {len(survivors[:args.top])} survived unseen data")
    if held_up:
        best = max(held_up, key=lambda c: c.score)
        print(f"\nbest survivor: {best.label} on {best.product} {best.timeframe} "
              f"at {best.risk:.0%} risk")
        print(best.result.summary())


if __name__ == "__main__":
    main()
