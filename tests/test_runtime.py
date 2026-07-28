"""Reliability plumbing: state recovery, single-instance lock, market hours,
journal reconciliation, and per-cycle error isolation."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from tradebot.brokers.base import BracketOrder, BrokerError, OrderSide, TradingMode
from tradebot.brokers.paper import PaperBroker
from tradebot.risk.journal import JournalEntry, TradeJournal
from tradebot.risk.limits import RiskLimits, RiskManager
from tradebot.runtime.cycle import TradingCycle
from tradebot.runtime.hours import (
    AlwaysOpenSchedule,
    ExchangeSchedule,
    ForexSchedule,
    is_tradable,
)
from tradebot.runtime.lock import AlreadyRunning, InstanceLock
from tradebot.runtime.state import StateStore
from tradebot.runtime.watchdog import Heartbeat, Watchdog
from tradebot.strategy.base import Enter, NoOpStrategy, Strategy


# ---------------------------------------------------------------------------
# State: atomic writes and self-healing
# ---------------------------------------------------------------------------

def test_state_round_trips(tmp_path):
    store = StateStore(tmp_path / "state.json")
    store.save({"positions": 3, "balance": 10_500.0})
    assert store.load().data["positions"] == 3


def test_missing_state_returns_defaults(tmp_path):
    store = StateStore(tmp_path / "absent.json", defaults={"balance": 10_000.0})
    result = store.load()
    assert result.data["balance"] == 10_000.0
    assert not result.recovered


def test_corrupt_state_is_quarantined_not_fatal(tmp_path):
    path = tmp_path / "state.json"
    path.write_text("{ this is not json at all", encoding="utf-8")

    store = StateStore(path, defaults={"balance": 10_000.0})
    result = store.load()

    assert result.recovered
    assert result.data["balance"] == 10_000.0        # fell back to defaults
    assert result.backup_path is not None
    assert result.backup_path.exists()               # bad file kept for inspection
    assert "corrupt" in result.backup_path.name


def test_non_object_state_is_treated_as_corrupt(tmp_path):
    path = tmp_path / "state.json"
    path.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
    assert StateStore(path).load().recovered


def test_no_temp_file_is_left_behind(tmp_path):
    store = StateStore(tmp_path / "state.json")
    store.save({"a": 1})
    assert list(tmp_path.glob("*.tmp")) == []


def test_update_merges_rather_than_replacing(tmp_path):
    store = StateStore(tmp_path / "state.json")
    store.save({"a": 1, "b": 2})
    merged = store.update(b=99)
    assert merged["a"] == 1 and merged["b"] == 99


# ---------------------------------------------------------------------------
# Single-instance lock
# ---------------------------------------------------------------------------

def test_lock_is_acquired_and_released(tmp_path):
    lock = InstanceLock(tmp_path / "bot.lock")
    with lock:
        assert lock.held
    assert not lock.held


def test_second_instance_is_refused(tmp_path):
    """The whole point: two copies against one account must be impossible."""
    path = tmp_path / "bot.lock"
    first = InstanceLock(path).acquire()
    try:
        with pytest.raises(AlreadyRunning):
            InstanceLock(path).acquire()
    finally:
        first.release()


def test_lock_is_reusable_after_release(tmp_path):
    path = tmp_path / "bot.lock"
    InstanceLock(path).acquire().release()
    second = InstanceLock(path).acquire()      # stale file must not block us
    assert second.held
    second.release()


def test_lock_records_the_holder(tmp_path):
    path = tmp_path / "bot.lock"
    lock = InstanceLock(path).acquire()
    try:
        assert "pid=" in path.read_text(encoding="utf-8")
    finally:
        lock.release()


# ---------------------------------------------------------------------------
# Market hours
# ---------------------------------------------------------------------------

def test_forex_closed_on_saturday():
    sat = datetime(2026, 3, 14, 12, 0, tzinfo=timezone.utc)
    assert not ForexSchedule().is_open(sat)


def test_forex_open_midweek():
    wed = datetime(2026, 3, 11, 12, 0, tzinfo=timezone.utc)
    assert ForexSchedule().is_open(wed)


def test_forex_closed_after_friday_close():
    # 23:00 UTC Friday is 18:00 New York, past the 17:00 close.
    fri_night = datetime(2026, 3, 13, 23, 0, tzinfo=timezone.utc)
    assert not ForexSchedule().is_open(fri_night)


def test_forex_closed_sunday_morning():
    sun_am = datetime(2026, 3, 15, 10, 0, tzinfo=timezone.utc)
    assert not ForexSchedule().is_open(sun_am)


def test_crypto_never_closes():
    sat = datetime(2026, 3, 14, 3, 0, tzinfo=timezone.utc)
    assert AlwaysOpenSchedule().is_open(sat)
    assert is_tradable("BTCUSD", sat).is_open


def test_exchange_closed_outside_session():
    # 08:00 New York, before the 09:30 open.
    pre = datetime(2026, 3, 11, 12, 0, tzinfo=timezone.utc)
    assert not ExchangeSchedule().is_open(pre)


def test_exchange_honours_holidays():
    schedule = ExchangeSchedule(holidays={"2026-03-11"})
    midday = datetime(2026, 3, 11, 15, 0, tzinfo=timezone.utc)
    assert not schedule.is_open(midday)


def test_closed_market_gives_a_reason_rather_than_raising():
    sat = datetime(2026, 3, 14, 12, 0, tzinfo=timezone.utc)
    status = is_tradable("EURUSD", sat)
    assert not status.is_open
    assert "weekend" in status.reason


# ---------------------------------------------------------------------------
# Journal and reconciliation
# ---------------------------------------------------------------------------

def journal_with(tmp_path, *pnls: float) -> TradeJournal:
    journal = TradeJournal(tmp_path / "journal.jsonl", starting_balance=10_000.0)
    for i, pnl in enumerate(pnls):
        journal.record(JournalEntry(
            ticket=str(i), symbol="XAUUSD", side="buy", lots=0.1,
            entry_price=2000.0, exit_price=2010.0,
            opened_at=datetime.now(timezone.utc).isoformat(),
            closed_at=datetime.now(timezone.utc).isoformat(),
            realized_pnl=pnl,
        ))
    return journal


def test_journal_totals_realized_pnl(tmp_path):
    journal = journal_with(tmp_path, 100.0, -40.0, 25.0)
    assert journal.realized_pnl() == pytest.approx(85.0)
    assert journal.expected_balance() == pytest.approx(10_085.0)


def test_reconciliation_passes_when_the_numbers_agree(tmp_path):
    journal = journal_with(tmp_path, 100.0, -40.0)
    assert journal.reconcile(10_060.0).matches


def test_reconciliation_fails_on_a_100x_error(tmp_path):
    """The exact failure the contract multiplier bug would produce."""
    journal = journal_with(tmp_path, 10_000.0)       # should have been 100.00
    result = journal.reconcile(10_100.0)
    assert not result.matches
    assert result.difference == pytest.approx(9_900.0)
    assert "MISMATCH" in result.describe()


def test_journal_survives_a_torn_final_line(tmp_path):
    journal = journal_with(tmp_path, 100.0, 50.0)
    with journal.path.open("a", encoding="utf-8") as fh:
        fh.write('{"ticket": "3", "symbol": "XAU')     # crashed mid-write
    assert len(journal.entries()) == 2
    assert journal.realized_pnl() == pytest.approx(150.0)


def test_journal_stats(tmp_path):
    journal = journal_with(tmp_path, 100.0, -50.0, 200.0, -25.0)
    stats = journal.stats()
    assert stats["trades"] == 4
    assert stats["wins"] == 2
    assert stats["win_rate"] == pytest.approx(0.5)
    assert stats["profit_factor"] == pytest.approx(300.0 / 75.0)


# ---------------------------------------------------------------------------
# Cycle error isolation
# ---------------------------------------------------------------------------

class ExplodingStrategy(Strategy):
    """Stands in for a strategy bug or a malformed tick."""

    name = "exploding"

    def evaluate(self, context):
        raise ValueError("bad tick")


def build_cycle(tmp_path, strategy, symbols=("XAUUSD",)):
    broker = PaperBroker(starting_balance=10_000.0, spread=0.0)
    broker.connect()
    broker.set_price("XAUUSD", 2000.0)
    broker.feed_candles("XAUUSD", strategy.timeframe, [])
    return TradingCycle(
        broker=broker,
        strategy=strategy,
        risk=RiskManager(RiskLimits()),
        journal=TradeJournal(tmp_path / "j.jsonl", starting_balance=10_000.0),
        symbols=list(symbols),
    )


def test_cycle_survives_a_strategy_exception(tmp_path):
    cycle = build_cycle(tmp_path, ExplodingStrategy())
    weekday = datetime(2026, 3, 11, 15, 0, tzinfo=timezone.utc)

    report = cycle.run_once(weekday)          # must not raise

    assert not report.ok
    assert any("bad tick" in e for e in report.errors)
    assert report.finished_at is not None


def test_cycle_reports_clean_when_nothing_goes_wrong(tmp_path):
    cycle = build_cycle(tmp_path, NoOpStrategy())
    weekday = datetime(2026, 3, 11, 15, 0, tzinfo=timezone.utc)
    report = cycle.run_once(weekday)
    assert report.ok
    assert report.orders_submitted == 0


def test_cycle_skips_symbols_outside_market_hours(tmp_path):
    cycle = build_cycle(tmp_path, NoOpStrategy())
    saturday = datetime(2026, 3, 14, 12, 0, tzinfo=timezone.utc)
    report = cycle.run_once(saturday)
    assert "XAUUSD" in report.symbols_skipped
    assert report.symbols_checked == []


def test_one_bad_symbol_does_not_stop_the_others(tmp_path):
    cycle = build_cycle(tmp_path, NoOpStrategy(), symbols=("XAUUSD", "NOTREAL"))
    weekday = datetime(2026, 3, 11, 15, 0, tzinfo=timezone.utc)
    report = cycle.run_once(weekday)
    assert "XAUUSD" in report.symbols_checked      # good symbol still processed
    assert report.errors                            # bad one recorded, not raised


# ---------------------------------------------------------------------------
# Watchdog
# ---------------------------------------------------------------------------

def test_fresh_heartbeat_is_healthy(tmp_path):
    hb = Heartbeat(tmp_path / "hb.json")
    hb.beat()
    assert hb.status(timedelta(minutes=15)).healthy


def test_stale_heartbeat_is_detected(tmp_path):
    hb = Heartbeat(tmp_path / "hb.json")
    hb.beat()
    later = datetime.now(timezone.utc) + timedelta(hours=2)
    status = hb.status(timedelta(minutes=15), now=later)
    assert status.stale
    assert not status.healthy


def test_never_started_counts_as_stale(tmp_path):
    hb = Heartbeat(tmp_path / "hb.json")
    assert hb.status(timedelta(minutes=15)).stale


def test_watchdog_does_not_restart_a_healthy_job(tmp_path):
    hb = Heartbeat(tmp_path / "hb.json")
    hb.beat()
    dog = Watchdog(hb, max_age=timedelta(minutes=15),
                   restart_command=["/bin/true"], state_path=tmp_path / "w.json")
    assert not dog.check().stale


def test_watchdog_rate_limits_restarts(tmp_path):
    """A crash loop must not become a fork bomb."""
    hb = Heartbeat(tmp_path / "hb.json")
    dog = Watchdog(hb, max_age=timedelta(seconds=1),
                   restart_command=["/bin/true"], max_restarts_per_hour=2,
                   state_path=tmp_path / "w.json")
    now = datetime.now(timezone.utc)
    dog.store.save({"restarts": [now.isoformat(), now.isoformat()]})
    assert not dog._may_restart(now)
