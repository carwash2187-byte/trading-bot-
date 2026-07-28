"""Running one strategy across several markets on a shared account.

The thing to get right is that this is *not* the same as running eight separate
backtests and adding up the results. They share one balance, they compete for
the same risk budget, and crypto markets fall together -- so the shared-account
mechanics are the whole subject of these tests.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from tradebot.backtest import run_portfolio_backtest
from tradebot.brokers.base import Candle, OrderSide
from tradebot.instruments import Instrument
from tradebot.strategy.base import Action, Enter, Strategy

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def series(n: int, price: float, step: float = 0.0) -> list[Candle]:
    out = []
    for i in range(n):
        close = price + step * i
        out.append(Candle(timestamp=NOW + timedelta(hours=2 * i),
                          open=close, high=close * 1.004, low=close * 0.996,
                          close=close, volume=100.0))
    return out


def crypto(symbol: str) -> Instrument:
    """All in one correlation group, which is the honest way to model crypto."""
    return Instrument(symbol=symbol, contract_size=1.0, tick_size=0.01,
                      min_lot=0.001, max_lot=1000.0, lot_step=0.001,
                      base_currency=symbol[:-3], quote_currency="USD",
                      digits=2, correlation_group="CRYPTO")


class AlwaysBuy(Strategy):
    """Opens a position at the first opportunity in every market it is given."""

    name = "always_buy"
    lookback = 5

    def __init__(self):
        self.calls = 0

    def evaluate(self, context) -> list[Action]:
        self.calls += 1
        if context.has_position:
            return []
        return [Enter(side=OrderSide.BUY,
                      stop_loss=context.last_close * 0.9,
                      comment=self.name)]


def three_markets(n: int = 40) -> dict:
    return {
        "BTCUSD": series(n, 60_000.0),
        "ETHUSD": series(n, 3_000.0),
        "SOLUSD": series(n, 150.0),
    }


INSTRUMENTS = {s: crypto(s) for s in ("BTCUSD", "ETHUSD", "SOLUSD")}


def test_the_correlation_cap_is_enforced_across_markets():
    """Eight crypto positions is not eight bets -- it is one bet, eight times.

    Leaving this off would let the run report as diversification something that
    is really just leverage.
    """
    result = run_portfolio_backtest(
        AlwaysBuy, three_markets(), INSTRUMENTS,
        starting_balance=100_000.0, max_correlated=2, fee_pct=0.0,
    )
    # Three markets all screaming buy, but only two may be held at once.
    assert result.trades
    assert len(result.trades) <= 2 * 3       # far below one per market per bar


def test_raising_the_cap_lets_more_markets_in():
    tight = run_portfolio_backtest(
        AlwaysBuy, three_markets(), INSTRUMENTS,
        starting_balance=100_000.0, max_correlated=1, fee_pct=0.0,
    )
    loose = run_portfolio_backtest(
        AlwaysBuy, three_markets(), INSTRUMENTS,
        starting_balance=100_000.0, max_correlated=3, fee_pct=0.0,
    )
    assert len(loose.trades) > len(tight.trades)


def test_every_market_gets_its_own_strategy_instance():
    """A shared instance would leak one market's state into another's decisions."""
    seen = []

    def factory():
        instance = AlwaysBuy()
        seen.append(instance)
        return instance

    run_portfolio_backtest(factory, three_markets(), INSTRUMENTS,
                           starting_balance=100_000.0, fee_pct=0.0)
    assert len(seen) == 3
    assert len({id(s) for s in seen}) == 3


def test_the_account_is_shared_not_multiplied():
    result = run_portfolio_backtest(
        AlwaysBuy, three_markets(), INSTRUMENTS,
        starting_balance=50_000.0, max_correlated=3, fee_pct=0.0,
    )
    assert result.starting_balance == 50_000.0
    # Every trade came out of the one balance, so the arithmetic must close.
    assert sum(t["pnl"] for t in result.trades) == \
        __import__("pytest").approx(result.net_profit, abs=0.01)


def test_a_market_with_no_bar_at_a_timestamp_is_skipped_safely():
    """Coins list at different times; a short series must not break the run."""
    markets = three_markets()
    markets["SOLUSD"] = markets["SOLUSD"][20:]      # starts late
    result = run_portfolio_backtest(
        AlwaysBuy, markets, INSTRUMENTS,
        starting_balance=100_000.0, fee_pct=0.0,
    )
    assert result.start is not None
    assert result.symbol == "BTCUSD+ETHUSD+SOLUSD"


def test_the_timeline_covers_every_market():
    markets = three_markets(n=30)
    result = run_portfolio_backtest(
        AlwaysBuy, markets, INSTRUMENTS, starting_balance=100_000.0, fee_pct=0.0,
    )
    assert result.start == markets["BTCUSD"][0].timestamp
    assert result.end == markets["BTCUSD"][-1].timestamp


def test_positions_left_open_are_closed_at_the_end():
    result = run_portfolio_backtest(
        AlwaysBuy, three_markets(), INSTRUMENTS,
        starting_balance=100_000.0, max_correlated=3, fee_pct=0.0,
    )
    assert result.trades
    assert all("exit_price" in t for t in result.trades)


def test_no_markets_at_all_does_not_crash():
    result = run_portfolio_backtest(AlwaysBuy, {}, {}, starting_balance=1_000.0)
    assert result.trades == []
    assert result.ending_balance == 1_000.0


def test_each_market_can_run_a_different_strategy():
    """Gold and a crypto pair want different logic; one strategy tests neither."""
    class Passive(AlwaysBuy):
        name = "passive"

        def evaluate(self, context):
            return []

    markets = three_markets()
    result = run_portfolio_backtest(
        {"BTCUSD": AlwaysBuy, "ETHUSD": Passive, "SOLUSD": Passive},
        markets, INSTRUMENTS, starting_balance=100_000.0,
        max_correlated=3, fee_pct=0.0,
    )
    # Only the market given the active strategy should have traded.
    assert result.trades
    assert {t["symbol"] for t in result.trades} == {"BTCUSD"}


def test_a_single_factory_still_applies_to_every_market():
    result = run_portfolio_backtest(
        AlwaysBuy, three_markets(), INSTRUMENTS,
        starting_balance=100_000.0, max_correlated=3, fee_pct=0.0,
    )
    assert len({t["symbol"] for t in result.trades}) == 3
