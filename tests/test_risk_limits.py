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


# These tests verify the BREAKER MECHANISM -- that a daily loss trips, stays
# tripped, resets on a new day, and projects a full loss before allowing an entry.
# They are not a statement about what the limits should be.
#
# So they pin their own thresholds rather than reading the defaults. The defaults
# used to be 3% and 6%, inherited from a prop firm's rulebook, and these tests
# quietly depended on them; when the production defaults were loosened so that
# MambaFX's own "two losses and we're done for the day" rule governs instead, eight
# tests failed while the logic they cover was untouched. A test that breaks when a
# policy default changes is testing the default, not the mechanism.
TIGHT = RiskLimits(daily_loss_limit=0.03, max_drawdown_limit=0.06)


def fresh(limits: RiskLimits | None = None, equity: float = 10_000.0) -> RiskManager:
    rm = RiskManager(limits or TIGHT)
    rm.update_equity(equity, NOW)
    return rm


# -- daily loss -------------------------------------------------------------

def test_daily_loss_allows_trading_while_a_full_loss_stays_inside():
    """Entries are judged on where a FULL loss would land, not on where we are.

    The stop sits at 90% of the 3% limit (2.7%), and the next trade risks 1%,
    so entries are allowed only while today's loss plus one full trade-loss
    stays under 2.7% -- that is, down to about -1.7% on the day. This replaced
    a rule that allowed entries right up against the line, where the trade
    being entered could itself carry the account through it.
    """
    rm = fresh()                                   # 3% daily limit
    rm.update_equity(9_850.0, NOW)                 # -1.5%: projected -2.5%, fine
    assert rm.check_entry(9_850.0, "EURUSD", None, []).allowed

    rm2 = fresh()
    rm2.update_equity(9_790.0, NOW)                # -2.1%: projected -3.1%, no
    assert not rm2.check_entry(9_790.0, "EURUSD", None, []).allowed


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


def test_drawdown_allows_trading_while_a_full_loss_stays_inside():
    """Same one-full-loss headroom as the daily breaker, against the peak."""
    rm = fresh()
    rm.update_equity(20_000.0, NOW)
    rm.update_equity(19_200.0, NOW)                # -4%: projected -5%, fine
    assert rm.check_entry(19_200.0, "EURUSD", None, []).allowed

    rm2 = fresh()
    rm2.update_equity(20_000.0, NOW)
    rm2.update_equity(19_080.0, NOW)               # -4.6%: projected -5.6%, no
    assert not rm2.check_entry(19_080.0, "EURUSD", None, []).allowed


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


# ---------------------------------------------------------------------------
# Gold's clock is not forex's clock
# ---------------------------------------------------------------------------

def test_gold_stands_aside_for_the_full_metals_break():
    """Metals close 17:00-18:00 New York daily. On the forex clock the bot
    spent that hour quoting a shut market and placing orders into it -- and a
    rejected order now fails the run loudly, so this was a nightly false
    alarm waiting to happen."""
    from datetime import datetime, timezone

    from tradebot.runtime.hours import is_tradable

    # 17:30 New York on a Tuesday == 21:30 UTC in July (EDT).
    dead_hour = datetime(2026, 7, 28, 21, 30, tzinfo=timezone.utc)
    assert not is_tradable("XAUUSD", dead_hour).is_open
    # Forex is open at that moment; only metals rest.
    assert is_tradable("EURUSD", dead_hour).is_open

    # 18:30 New York: metals are back.
    after = datetime(2026, 7, 28, 22, 30, tzinfo=timezone.utc)
    assert is_tradable("XAUUSD", after).is_open


def test_gold_opens_an_hour_after_forex_on_sunday():
    from datetime import datetime, timezone

    from tradebot.runtime.hours import is_tradable

    # Sunday 17:30 New York == 21:30 UTC: forex open, metals not yet.
    sunday = datetime(2026, 7, 26, 21, 30, tzinfo=timezone.utc)
    assert is_tradable("EURUSD", sunday).is_open
    assert not is_tradable("XAUUSD", sunday).is_open
