"""Circuit breakers: they must trip when they should, and not before."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from tradebot.brokers.base import OrderSide, Position
from tradebot.risk.limits import (
    CORRELATION,
    DAILY_LOSS,
    MAX_DRAWDOWN,
    RiskLimits,
    RiskManager,
    RiskState,
)

NOW = datetime(2026, 3, 10, 12, 0, tzinfo=timezone.utc)


def make_position(symbol: str, ticket: str = "1") -> Position:
    return Position(
        ticket=ticket, symbol=symbol, side=OrderSide.BUY, lots=0.1,
        entry_price=1.0, stop_loss=0.99, take_profit=None, opened_at=NOW,
    )


def fresh(limits: RiskLimits | None = None, equity: float = 10_000.0) -> RiskManager:
    rm = RiskManager(limits or RiskLimits())
    rm.update_equity(equity, NOW)
    return rm


# -- daily loss -------------------------------------------------------------

def test_daily_loss_allows_trading_just_under_the_limit():
    rm = fresh()                                   # 3% daily limit
    rm.update_equity(9_750.0, NOW)                 # -2.5%
    assert rm.check_entry(9_750.0, "EURUSD", None, []).allowed


def test_daily_loss_trips_exactly_at_the_limit():
    rm = fresh()
    rm.update_equity(9_700.0, NOW)                 # -3.0%
    decision = rm.check_entry(9_700.0, "EURUSD", None, [])
    assert not decision.allowed
    assert decision.reason == DAILY_LOSS


def test_daily_loss_stays_tripped_for_the_rest_of_the_day():
    rm = fresh()
    rm.update_equity(9_600.0, NOW)
    rm.check_entry(9_600.0, "EURUSD", None, [])    # trips
    # Equity recovers, but the day is still done.
    rm.update_equity(9_950.0, NOW + timedelta(hours=2))
    assert not rm.check_entry(9_950.0, "EURUSD", None, []).allowed


def test_daily_loss_resets_on_the_next_day():
    rm = fresh()
    rm.update_equity(9_600.0, NOW)
    rm.check_entry(9_600.0, "EURUSD", None, [])
    assert rm.state.halted

    tomorrow = NOW + timedelta(days=1)
    rm.update_equity(9_600.0, tomorrow)
    assert not rm.state.halted
    assert rm.check_entry(9_600.0, "EURUSD", None, []).allowed


# -- max drawdown -----------------------------------------------------------

def test_drawdown_measured_from_the_peak_not_the_start():
    rm = fresh()
    rm.update_equity(20_000.0, NOW)                # new high-water mark
    # Down 6% from 20k is 18.8k, even though that is well above the 10k start.
    rm.update_equity(18_800.0, NOW)
    decision = rm.check_entry(18_800.0, "EURUSD", None, [])
    assert not decision.allowed
    assert decision.reason == MAX_DRAWDOWN


def test_drawdown_does_not_trip_just_under_the_limit():
    rm = fresh()
    rm.update_equity(20_000.0, NOW)
    rm.update_equity(19_000.0, NOW)                # -5%
    assert rm.check_entry(19_000.0, "EURUSD", None, []).allowed


def test_drawdown_halt_does_not_clear_on_a_new_day():
    """A daily halt expires overnight; an account-level one must not."""
    rm = fresh()
    rm.update_equity(20_000.0, NOW)
    rm.update_equity(18_000.0, NOW)
    rm.check_entry(18_000.0, "EURUSD", None, [])
    assert rm.state.halt_reason == MAX_DRAWDOWN

    rm.update_equity(18_000.0, NOW + timedelta(days=3))
    assert rm.state.halted
    assert not rm.check_entry(18_000.0, "EURUSD", None, []).allowed


def test_operator_can_clear_a_drawdown_halt():
    rm = fresh()
    rm.update_equity(20_000.0, NOW)
    rm.update_equity(18_000.0, NOW)
    rm.check_entry(18_000.0, "EURUSD", None, [])
    rm.reset_halt()
    rm.reset_peak(18_000.0)
    assert rm.check_entry(18_000.0, "EURUSD", None, []).allowed


# -- correlation and count caps --------------------------------------------

def test_correlation_cap_blocks_a_third_jpy_pair():
    rm = fresh(RiskLimits(max_correlated_positions=2))
    open_positions = [make_position("USDJPY", "1"), make_position("EURJPY", "2")]
    groups = {"USDJPY": "JPY", "EURJPY": "JPY"}
    decision = rm.check_entry(10_000.0, "GBPJPY", "JPY", open_positions, groups)
    assert not decision.allowed
    assert decision.reason == CORRELATION


def test_correlation_cap_allows_an_unrelated_symbol():
    rm = fresh(RiskLimits(max_correlated_positions=2))
    open_positions = [make_position("USDJPY", "1"), make_position("EURJPY", "2")]
    groups = {"USDJPY": "JPY", "EURJPY": "JPY"}
    assert rm.check_entry(10_000.0, "XAUUSD", "METALS", open_positions, groups).allowed


def test_total_position_cap_applies_across_all_groups():
    rm = fresh(RiskLimits(max_total_positions=2))
    open_positions = [make_position("EURUSD", "1"), make_position("XAUUSD", "2")]
    assert not rm.check_entry(10_000.0, "BTCUSD", "CRYPTO", open_positions).allowed


# -- configuration sanity ---------------------------------------------------

def test_daily_limit_above_account_limit_is_rejected():
    """A daily breaker looser than the account breaker could never fire."""
    with pytest.raises(ValueError):
        RiskLimits(daily_loss_limit=0.10, max_drawdown_limit=0.06)


def test_state_round_trips_through_a_dict():
    state = RiskState(peak_equity=12_345.6, day_start_equity=12_000.0,
                      current_day="2026-03-10", halted=True, halt_reason=DAILY_LOSS)
    restored = RiskState.from_dict(state.to_dict())
    assert restored == state
