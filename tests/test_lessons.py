"""Learning across funded accounts.

The behaviour that matters is restraint: it must not change size on thin
evidence, and it must not swing wildly when one account has a bad run. A
sizing rule that overreacts is worse than a fixed size.
"""

from __future__ import annotations

import pytest

from tradebot.portfolio.lessons import BREACHED, RETIRED, LessonBook


def book(tmp_path, **kwargs):
    return LessonBook(path=tmp_path / "lessons.json", **kwargs)


def add(lb, size, days, withdrawn, payouts=1, ended=BREACHED):
    return lb.record_account(size=size, days_lived=days, withdrawn=withdrawn,
                             payouts=payouts, ended=ended)


# ---------------------------------------------------------------------------
# Restraint
# ---------------------------------------------------------------------------

def test_starts_at_the_default_with_no_history(tmp_path):
    size, why = book(tmp_path).recommend_size()
    assert size == 3.0
    assert "need 3" in why


def test_one_bad_account_does_not_change_anything(tmp_path):
    """A single early breach is a bad run, not evidence."""
    lb = book(tmp_path)
    add(lb, size=3.0, days=2, withdrawn=0.0, payouts=0)
    size, why = lb.recommend_size()
    assert size == 3.0
    assert "need 3" in why


def test_size_moves_only_one_step_at_a_time(tmp_path):
    """Even overwhelming evidence cannot jump the size in one go.

    5.0x looks hugely better here, but the account just run was at 1.0x, so the
    next one may only step to 1.5x. Jumping straight there would let a lucky
    run at a barely-tested size dominate everything after it.
    """
    lb = book(tmp_path, default_size=1.0, step=0.5)
    for _ in range(3):
        add(lb, size=5.0, days=40, withdrawn=3000.0)   # far better per day
    for _ in range(3):
        add(lb, size=1.0, days=60, withdrawn=200.0)    # ...but this ran last
    size, _ = lb.recommend_size()
    assert size == pytest.approx(1.5)


def test_never_exceeds_the_ceiling(tmp_path):
    lb = book(tmp_path, ceiling=4.0)
    for _ in range(4):
        add(lb, size=4.0, days=50, withdrawn=5000.0)
    size, _ = lb.recommend_size()
    assert size <= 4.0


def test_never_drops_below_the_floor(tmp_path):
    lb = book(tmp_path, floor=1.0)
    for _ in range(4):
        add(lb, size=1.0, days=3, withdrawn=0.0, payouts=0)
    size, _ = lb.recommend_size()
    assert size >= 1.0


# ---------------------------------------------------------------------------
# Actually learning
# ---------------------------------------------------------------------------

def test_moves_toward_the_size_that_earns_most_per_day(tmp_path):
    lb = book(tmp_path, default_size=2.0)
    for _ in range(3):
        add(lb, size=2.0, days=60, withdrawn=400.0)     # $5.00/day net
    for _ in range(3):
        add(lb, size=3.0, days=40, withdrawn=900.0)     # $20.00/day net
    size, why = lb.recommend_size()
    assert size > 3.0 - 0.01
    assert "3.0x earns the most" in why


def test_backs_away_from_a_size_that_keeps_dying(tmp_path):
    """Big payouts do not justify a size that dies before collecting them."""
    lb = book(tmp_path)
    for _ in range(3):
        add(lb, size=2.0, days=60, withdrawn=800.0)     # steady
    for _ in range(3):
        add(lb, size=4.0, days=3, withdrawn=50.0, payouts=0)   # dies fast
    size, _ = lb.recommend_size()
    assert size < 4.0


def test_money_per_day_beats_money_per_account(tmp_path):
    """A size earning more overall but living far longer can still be worse."""
    lb = book(tmp_path, default_size=2.0)
    for _ in range(3):
        add(lb, size=2.0, days=200, withdrawn=1000.0)   # $4.50/day
    for _ in range(3):
        add(lb, size=3.0, days=20, withdrawn=600.0)     # $25.00/day
    verdicts = lb.verdicts()
    assert verdicts[3.0].per_day > verdicts[2.0].per_day
    size, _ = lb.recommend_size()
    assert size > 2.0


def test_the_fee_is_counted_against_each_account(tmp_path):
    lb = book(tmp_path)
    rec = add(lb, size=3.0, days=10, withdrawn=100.0)
    assert rec.net == 0.0          # withdrew exactly the fee back
    rec2 = add(lb, size=3.0, days=10, withdrawn=40.0)
    assert rec2.net == -60.0       # a real loss, not a small win


def test_retired_accounts_do_not_count_as_breaches(tmp_path):
    lb = book(tmp_path)
    for _ in range(3):
        add(lb, size=3.0, days=30, withdrawn=500.0, ended=RETIRED)
    assert lb.verdicts()[3.0].breach_rate == 0.0


# ---------------------------------------------------------------------------
# Persistence — the whole point is surviving the account it learned from
# ---------------------------------------------------------------------------

def test_history_outlives_the_account(tmp_path):
    lb = book(tmp_path)
    for _ in range(3):
        add(lb, size=3.0, days=40, withdrawn=700.0)

    revived = book(tmp_path)                    # new account, new process
    assert len(revived.records) == 3
    assert revived.verdicts()[3.0].accounts == 3


def test_a_corrupt_row_does_not_destroy_the_history(tmp_path):
    lb = book(tmp_path)
    add(lb, size=3.0, days=40, withdrawn=700.0)
    raw = lb.store.load().data
    raw["accounts"].append({"size": "not a number"})
    lb.store.save(raw)

    revived = book(tmp_path)
    assert len(revived.records) == 1            # good row kept, bad row dropped


def test_report_is_readable_with_no_history(tmp_path):
    assert "no accounts" in book(tmp_path).report()
