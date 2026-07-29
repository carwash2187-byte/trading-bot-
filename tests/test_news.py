"""News calendar and high-impact event detection timing."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from tradebot.news.calendar import (
    EconomicCalendar,
    Impact,
    NewsDetector,
    NewsEvent,
)

NOW = datetime(2026, 3, 10, 12, 0, 0, tzinfo=timezone.utc)


def event(minutes_from_now: float, impact=Impact.HIGH, currency="USD", title="CPI") -> NewsEvent:
    return NewsEvent(
        title=title,
        currency=currency,
        scheduled_at=NOW + timedelta(minutes=minutes_from_now),
        impact=impact,
    )


def calendar_with(*events: NewsEvent, tmp_path=None) -> EconomicCalendar:
    cal = EconomicCalendar(cache_path=(tmp_path or "/tmp") + "/cal.json"
                           if isinstance(tmp_path, str) else (tmp_path / "cal.json"
                                                              if tmp_path else "/tmp/cal.json"))
    cal.load_events(list(events))
    return cal


# -- impact parsing ---------------------------------------------------------

@pytest.mark.parametrize("raw,expected", [
    ("high", Impact.HIGH), ("HIGH", Impact.HIGH), ("3", Impact.HIGH), ("red", Impact.HIGH),
    ("medium", Impact.MEDIUM), ("2", Impact.MEDIUM),
    ("low", Impact.LOW), ("anything else", Impact.LOW),
])
def test_impact_parsing(raw, expected):
    assert Impact.parse(raw) == expected


def test_impact_is_ordered():
    assert Impact.HIGH > Impact.MEDIUM > Impact.LOW


# -- detection windows ------------------------------------------------------

def test_event_five_minutes_out_is_imminent(tmp_path):
    cal = calendar_with(event(5), tmp_path=tmp_path)
    window = NewsDetector(cal, pre_window=300).check("EURUSD", NOW)
    assert window.is_imminent
    assert window.active
    assert window.seconds_until == pytest.approx(300.0)


def test_event_twenty_minutes_out_is_not_imminent(tmp_path):
    cal = calendar_with(event(20), tmp_path=tmp_path)
    window = NewsDetector(cal, pre_window=300).check("EURUSD", NOW)
    assert not window.is_imminent
    assert window.quiet


def test_event_two_minutes_ago_is_fresh(tmp_path):
    cal = calendar_with(event(-2), tmp_path=tmp_path)
    window = NewsDetector(cal, post_window=300).check("EURUSD", NOW)
    assert window.is_fresh
    assert window.active


def test_event_an_hour_ago_is_stale(tmp_path):
    cal = calendar_with(event(-60), tmp_path=tmp_path)
    window = NewsDetector(cal, post_window=300).check("EURUSD", NOW)
    assert not window.is_fresh
    assert window.quiet


# -- filtering --------------------------------------------------------------

def test_low_impact_events_are_ignored_at_high_threshold(tmp_path):
    cal = calendar_with(event(2, impact=Impact.LOW), tmp_path=tmp_path)
    detector = NewsDetector(cal, min_impact=Impact.HIGH)
    assert detector.check("EURUSD", NOW).quiet


def test_medium_impact_seen_when_threshold_is_medium(tmp_path):
    cal = calendar_with(event(2, impact=Impact.MEDIUM), tmp_path=tmp_path)
    detector = NewsDetector(cal, min_impact=Impact.MEDIUM)
    assert detector.check("EURUSD", NOW).is_imminent


def test_event_only_affects_symbols_containing_its_currency(tmp_path):
    cal = calendar_with(event(2, currency="JPY"), tmp_path=tmp_path)
    detector = NewsDetector(cal)
    assert detector.check("USDJPY", NOW).is_imminent
    assert detector.check("EURGBP", NOW).quiet


def test_affects_matches_either_side_of_the_pair():
    usd = event(0, currency="USD")
    assert usd.affects("EURUSD")
    assert usd.affects("USDJPY")
    assert not usd.affects("EURGBP")


# -- the fast path ----------------------------------------------------------

def test_just_fired_catches_a_release_within_seconds(tmp_path):
    cal = calendar_with(
        NewsEvent("NFP", "USD", NOW - timedelta(seconds=3), Impact.HIGH), tmp_path=tmp_path
    )
    detector = NewsDetector(cal)
    assert detector.just_fired("EURUSD", within_seconds=5, now=NOW) is not None


def test_just_fired_ignores_an_older_release(tmp_path):
    cal = calendar_with(
        NewsEvent("NFP", "USD", NOW - timedelta(seconds=30), Impact.HIGH), tmp_path=tmp_path
    )
    detector = NewsDetector(cal)
    assert detector.just_fired("EURUSD", within_seconds=5, now=NOW) is None


def test_just_fired_ignores_an_upcoming_release(tmp_path):
    cal = calendar_with(event(1), tmp_path=tmp_path)
    detector = NewsDetector(cal)
    assert detector.just_fired("EURUSD", within_seconds=5, now=NOW) is None


def test_detection_is_fast_on_a_large_calendar(tmp_path):
    """Must be cheap enough to run every cycle, not once a day."""
    import time

    events = [event(i - 25_000, impact=Impact.HIGH) for i in range(50_000)]
    cal = calendar_with(*events, tmp_path=tmp_path)
    detector = NewsDetector(cal)

    # Measured against a baseline taken on the same machine at the same
    # moment, not against a wall-clock constant. An absolute threshold turns
    # any busy machine into a red test -- this one failed repeatedly while
    # unrelated work ran alongside it, which trains you to ignore the suite.
    #
    # What actually matters is that the check does not SCAN the calendar: it
    # must cost about the same over 50,000 events as over 50.
    small = NewsDetector(calendar_with(*events[:50], tmp_path=tmp_path / "s"))

    def cost(det):
        start = time.perf_counter()
        for _ in range(1_000):
            det.check("EURUSD", NOW)
        return time.perf_counter() - start

    cost(small)                        # warm the code paths for both
    cost(detector)
    baseline = cost(small)
    big = cost(detector)

    # A linear scan over 1,000x the events would be ~1,000x slower. Ten times
    # the baseline is loose enough to survive a loaded machine and tight
    # enough to catch a scan.
    assert big < max(baseline * 10, 0.05)


# -- loading and resilience -------------------------------------------------

def test_events_are_sorted_after_load(tmp_path):
    cal = calendar_with(event(30), event(-10), event(5), tmp_path=tmp_path)
    times = [e.scheduled_at for e in cal.events]
    assert times == sorted(times)


def test_in_range_returns_only_the_window(tmp_path):
    cal = calendar_with(event(-30), event(10), event(45), event(120), tmp_path=tmp_path)
    found = cal.in_range(NOW, NOW + timedelta(hours=1))
    assert len(found) == 2


def test_malformed_rows_are_skipped_not_fatal(tmp_path):
    cache = tmp_path / "cal.json"
    cache.write_text(json.dumps([
        {"title": "Good", "currency": "USD", "date": NOW.isoformat(), "impact": "high"},
        {"title": "Bad", "currency": "USD", "date": "not-a-date", "impact": "high"},
        {"nonsense": True},
    ]), encoding="utf-8")
    cal = EconomicCalendar(cache_path=cache)
    assert cal.load_from_cache() == 1


def test_missing_cache_loads_zero_rather_than_raising(tmp_path):
    cal = EconomicCalendar(cache_path=tmp_path / "absent.json")
    assert cal.load_from_cache() == 0
