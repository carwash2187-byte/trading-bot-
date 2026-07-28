"""The backtest engine.

These tests exist because a backtester that flatters a strategy is worse than
having none at all -- it produces confident numbers that are wrong, and the
error is invisible in the output. Each test below pins down one specific way a
backtest can lie in the strategy's favour.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from tradebot.backtest.engine import BacktestBroker, BacktestResult, run_backtest
from tradebot.brokers.base import BracketOrder, Candle, OrderSide
from tradebot.strategy.base import Action, Enter, Strategy

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def bar(o, h, l, c, i=0) -> Candle:
    return Candle(timestamp=NOW + timedelta(hours=2 * i), open=o, high=h,
                  low=l, close=c, volume=100.0)


def flat(n: int, price: float = 60_000.0, wobble: float = 50.0) -> list[Candle]:
    return [bar(price, price + wobble, price - wobble, price, i) for i in range(n)]


class BuyOnce(Strategy):
    """Enters long exactly once, then never acts again."""

    name = "buy_once"
    lookback = 10

    def __init__(self, stop_below: float = 500.0):
        self.stop_below = stop_below
        self.fired = False

    def evaluate(self, context) -> list[Action]:
        if self.fired or context.has_position:
            return []
        self.fired = True
        return [Enter(side=OrderSide.BUY,
                      stop_loss=context.last_close - self.stop_below,
                      comment=self.name)]


class Peeker(Strategy):
    """Records the last bar it was shown, so look-ahead becomes visible."""

    name = "peeker"
    lookback = 50

    def __init__(self):
        self.last_seen: list[datetime] = []
        self.widest = 0

    def evaluate(self, context) -> list[Action]:
        self.last_seen.append(context.candles[-1].timestamp)
        self.widest = max(self.widest, len(context.candles))
        return []


# ---------------------------------------------------------------------------
# The big one: stops must be checked against the bar's range
# ---------------------------------------------------------------------------

def test_a_stop_blown_through_midbar_is_honoured():
    """The single most flattering bug a backtester can have.

    Checking only closes lets a trade whose stop was passed mid-bar survive to
    a happier price. Here the bar dives far below the stop and recovers to
    close green -- a close-only engine would report an open winner.
    """
    candles = flat(12) + [
        bar(60_000, 60_100, 55_000, 60_050, 12),   # spike down through the stop
        bar(60_050, 61_000, 60_000, 60_900, 13),   # then a happy recovery
    ]
    result = run_backtest(BuyOnce(stop_below=500), candles,
                          starting_balance=20_000, warmup=10)

    assert len(result.trades) == 1
    trade = result.trades[0]
    assert trade["reason"] == "stop_loss"
    assert trade["pnl"] < 0


def test_the_adverse_extreme_is_assumed_to_come_first():
    """When a bar hits both the stop and the target, the stop wins.

    The path inside a bar is unknowable. Assuming the good side came first is
    how a losing strategy is made to look profitable.
    """
    broker = BacktestBroker(starting_balance=20_000, spread_pct=0.0, fee_pct=0.0)
    broker.connect()
    broker.set_price("BTCUSD", 60_000)
    broker.submit_bracket(BracketOrder(
        symbol="BTCUSD", side=OrderSide.BUY, lots=0.01,
        stop_loss=59_000, take_profit=61_000,
    ))
    # This bar reaches both levels.
    broker.advance("BTCUSD", bar(60_000, 61_500, 58_500, 60_000))

    assert len(broker.closed_trades) == 1
    assert broker.closed_trades[0]["reason"] == "stop_loss"


def test_a_short_stop_is_checked_against_the_high():
    broker = BacktestBroker(starting_balance=20_000, spread_pct=0.0, fee_pct=0.0)
    broker.connect()
    broker.set_price("BTCUSD", 60_000)
    broker.submit_bracket(BracketOrder(
        symbol="BTCUSD", side=OrderSide.SELL, lots=0.01, stop_loss=61_000,
    ))
    broker.advance("BTCUSD", bar(60_000, 61_500, 59_900, 60_000))

    assert len(broker.closed_trades) == 1
    assert broker.closed_trades[0]["reason"] == "stop_loss"


# ---------------------------------------------------------------------------
# Costs — a fee of zero is how published backtests lie
# ---------------------------------------------------------------------------

def test_every_fill_is_charged():
    broker = BacktestBroker(starting_balance=20_000, spread_pct=0.0, fee_pct=0.001)
    broker.connect()
    broker.set_price("BTCUSD", 60_000)
    broker.submit_bracket(BracketOrder(
        symbol="BTCUSD", side=OrderSide.BUY, lots=0.01, stop_loss=50_000,
    ))
    assert broker.fees_paid == pytest.approx(60_000 * 0.01 * 0.001)

    broker.close_position(list(broker._positions)[0])
    assert broker.fees_paid == pytest.approx(2 * 60_000 * 0.01 * 0.001)


def test_costs_come_out_of_real_money_not_just_a_counter():
    """Fees must move the balance, or the equity curve is fiction."""
    candles = flat(40)
    free = run_backtest(BuyOnce(), candles, starting_balance=20_000,
                        warmup=10, spread_pct=0.0, fee_pct=0.0)
    charged = run_backtest(BuyOnce(), candles, starting_balance=20_000,
                           warmup=10, spread_pct=0.0, fee_pct=0.002)

    assert charged.fees_paid > 0
    assert charged.ending_balance < free.ending_balance
    assert charged.net_profit < free.net_profit


def test_the_reported_trade_pnl_matches_the_account():
    """If per-trade numbers and the balance disagree, one of them is a lie."""
    result = run_backtest(BuyOnce(), flat(40), starting_balance=20_000,
                          warmup=10, fee_pct=0.001)
    from_trades = sum(t["pnl"] for t in result.trades)
    assert from_trades == pytest.approx(result.net_profit, abs=0.01)


def test_the_spread_is_a_percentage_not_a_fixed_amount():
    """A cash spread is meaningless over a window where BTC ranges 20x."""
    broker = BacktestBroker(spread_pct=0.001, fee_pct=0.0)
    broker.connect()
    broker.set_price("BTCUSD", 4_000)
    cheap_bid, cheap_ask = broker.get_price("BTCUSD")
    broker.set_price("BTCUSD", 60_000)
    rich_bid, rich_ask = broker.get_price("BTCUSD")

    assert (cheap_ask - cheap_bid) == pytest.approx(4.0)
    assert (rich_ask - rich_bid) == pytest.approx(60.0)


# ---------------------------------------------------------------------------
# Look-ahead
# ---------------------------------------------------------------------------

def test_a_strategy_never_sees_a_bar_that_has_not_closed():
    candles = flat(200)
    peeker = Peeker()
    run_backtest(peeker, candles, warmup=50)
    # Every evaluation's newest bar must be one the loop had already reached.
    stamps = [c.timestamp for c in candles]
    for i, seen in enumerate(peeker.last_seen):
        assert seen == stamps[50 + i]


def test_the_history_window_matches_what_the_live_bot_would_get():
    """Handing the backtest all of history would test a better-informed bot."""
    peeker = Peeker()
    run_backtest(peeker, flat(400), warmup=50)
    assert peeker.widest <= peeker.lookback


# ---------------------------------------------------------------------------
# Accounting
# ---------------------------------------------------------------------------

def test_an_open_position_is_closed_out_at_the_end():
    """Otherwise the result is flattered by a winner that was never realised."""
    result = run_backtest(BuyOnce(), flat(40), starting_balance=20_000, warmup=10)
    assert len(result.trades) == 1


def test_a_strategy_that_crashes_does_not_take_the_run_down():
    class Exploding(Strategy):
        name = "exploding"
        lookback = 10

        def evaluate(self, context):
            raise RuntimeError("boom")

    result = run_backtest(Exploding(), flat(40), warmup=10)
    assert result.trades == []
    assert result.ending_balance == result.starting_balance


def test_drawdown_measures_peak_to_trough_not_start_to_end():
    result = BacktestResult(
        strategy="x", symbol="BTCUSD", timeframe="2h", start=NOW,
        end=NOW + timedelta(days=10), starting_balance=100.0,
        ending_balance=100.0,
        equity_curve=[(NOW, 100.0), (NOW, 200.0), (NOW, 120.0), (NOW, 100.0)],
    )
    # Ends flat, but halved from its peak. Reporting 0% would hide the ride.
    assert result.max_drawdown_pct == pytest.approx(50.0)


def test_profit_factor_below_one_means_it_loses_money():
    result = BacktestResult(
        strategy="x", symbol="BTCUSD", timeframe="2h", start=NOW, end=NOW,
        starting_balance=100.0, ending_balance=90.0,
        trades=[{"pnl": 10.0}, {"pnl": -20.0}],
    )
    assert result.profit_factor == pytest.approx(0.5)
    assert result.win_rate == pytest.approx(50.0)


def test_an_empty_run_reports_nothing_rather_than_dividing_by_zero():
    result = run_backtest(BuyOnce(), [], starting_balance=20_000)
    assert result.trades == []
    assert result.win_rate == 0.0
    assert result.profit_factor == 0.0
    assert result.max_drawdown_pct == 0.0
