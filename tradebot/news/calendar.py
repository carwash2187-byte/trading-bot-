"""Economic calendar and fast high-impact event detection.

Two jobs, kept separate:

* :class:`EconomicCalendar` holds scheduled events, refreshed from a provider
  and cached to disk so a provider outage does not blind the bot.
* :class:`NewsDetector` answers "is a high-impact event imminent, or did one
  just fire?" in microseconds, so it can run on *every* trading cycle rather
  than once a day.

Speed matters because the whole point is reacting to a release faster than a
human can. Events are pre-sorted at load time and lookups use a binary search
over that sorted list, so a calendar with tens of thousands of events still
answers in well under a millisecond.

This module decides nothing about whether to trade the news. It reports what
is happening and when; the strategy chooses what to do about it.
"""

from __future__ import annotations

import bisect
import enum
import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path


class Impact(enum.IntEnum):
    """Ordered so comparisons like ``impact >= Impact.HIGH`` read naturally."""

    LOW = 1
    MEDIUM = 2
    HIGH = 3

    @classmethod
    def parse(cls, raw: object) -> "Impact":
        text = str(raw).strip().lower()
        if text in ("3", "high", "red"):
            return cls.HIGH
        if text in ("2", "medium", "med", "orange"):
            return cls.MEDIUM
        return cls.LOW


@dataclass(frozen=True)
class NewsEvent:
    """One scheduled economic release."""

    title: str
    currency: str
    scheduled_at: datetime      # always tz-aware UTC
    impact: Impact
    forecast: str = ""
    previous: str = ""
    actual: str = ""

    def affects(self, symbol: str) -> bool:
        """Whether this event's currency appears in the symbol."""
        return self.currency.upper() in symbol.upper()

    def seconds_until(self, now: datetime) -> float:
        return (self.scheduled_at - now).total_seconds()


@dataclass
class NewsWindow:
    """What the detector found on this cycle."""

    event: NewsEvent | None
    seconds_until: float        # negative once the event has passed
    is_imminent: bool           # inside the pre-release window
    is_fresh: bool              # inside the post-release window

    @property
    def active(self) -> bool:
        """True while the market is inside a news window either side."""
        return self.is_imminent or self.is_fresh

    @property
    def quiet(self) -> bool:
        return not self.active


class CalendarError(RuntimeError):
    """Raised when the calendar cannot be loaded from anywhere."""


class EconomicCalendar:
    """Scheduled events, kept sorted by time and cached on disk."""

    def __init__(self, cache_path: str | Path = "data/news/calendar.json") -> None:
        self.cache_path = Path(cache_path)
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self._events: list[NewsEvent] = []
        self._times: list[float] = []       # epoch seconds, parallel to _events
        self.last_refresh: datetime | None = None

    # -- loading ---------------------------------------------------------

    def load_events(self, events: list[NewsEvent]) -> None:
        """Replace the calendar with a sorted copy of ``events``."""
        self._events = sorted(events, key=lambda e: e.scheduled_at)
        self._times = [e.scheduled_at.timestamp() for e in self._events]
        self.last_refresh = datetime.now(timezone.utc)

    def refresh_from_url(self, url: str, timeout: float = 10.0) -> int:
        """Fetch the calendar, falling back to the disk cache on failure.

        Expects a JSON array of objects with ``title``, ``currency``, ``date``
        (ISO 8601) and ``impact``. Most public forex-calendar feeds either use
        this shape already or are a thin rename away.
        """
        try:
            with urllib.request.urlopen(url, timeout=timeout) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            events = [self._parse(row) for row in payload]
            events = [e for e in events if e is not None]
            self.load_events(events)  # type: ignore[arg-type]
            self._write_cache()
            return len(self._events)
        except (urllib.error.URLError, OSError, json.JSONDecodeError, ValueError) as err:
            # A provider outage must not stop the bot; fall back to cache.
            loaded = self.load_from_cache()
            if loaded == 0:
                raise CalendarError(f"calendar fetch failed and no cache: {err}") from err
            return loaded

    def load_from_cache(self) -> int:
        if not self.cache_path.exists():
            return 0
        try:
            payload = json.loads(self.cache_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return 0
        events = [self._parse(row) for row in payload]
        self.load_events([e for e in events if e is not None])  # type: ignore[arg-type]
        return len(self._events)

    def _write_cache(self) -> None:
        payload = [
            {
                "title": e.title,
                "currency": e.currency,
                "date": e.scheduled_at.isoformat(),
                "impact": int(e.impact),
                "forecast": e.forecast,
                "previous": e.previous,
                "actual": e.actual,
            }
            for e in self._events
        ]
        tmp = self.cache_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload), encoding="utf-8")
        tmp.replace(self.cache_path)   # atomic swap, never a half-written cache

    @staticmethod
    def _parse(row: dict) -> NewsEvent | None:
        try:
            raw_date = str(row.get("date") or row.get("scheduled_at"))
            ts = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            return NewsEvent(
                title=str(row.get("title") or row.get("event") or "unnamed"),
                currency=str(row.get("currency") or row.get("country") or "").upper(),
                scheduled_at=ts.astimezone(timezone.utc),
                impact=Impact.parse(row.get("impact", "low")),
                forecast=str(row.get("forecast") or ""),
                previous=str(row.get("previous") or ""),
                actual=str(row.get("actual") or ""),
            )
        except (ValueError, TypeError, AttributeError):
            return None   # one malformed row must not poison the whole feed

    # -- queries ---------------------------------------------------------

    def __len__(self) -> int:
        return len(self._events)

    @property
    def events(self) -> list[NewsEvent]:
        return list(self._events)

    def in_range(self, start: datetime, end: datetime) -> list[NewsEvent]:
        """Events scheduled within ``[start, end]``. O(log n) plus the slice."""
        lo = bisect.bisect_left(self._times, start.timestamp())
        hi = bisect.bisect_right(self._times, end.timestamp())
        return self._events[lo:hi]

    def next_event(
        self, now: datetime, min_impact: Impact = Impact.LOW, symbol: str | None = None
    ) -> NewsEvent | None:
        """The soonest upcoming event matching the filters."""
        idx = bisect.bisect_left(self._times, now.timestamp())
        for event in self._events[idx:]:
            if event.impact < min_impact:
                continue
            if symbol and not event.affects(symbol):
                continue
            return event
        return None

    def last_event(
        self, now: datetime, min_impact: Impact = Impact.LOW, symbol: str | None = None
    ) -> NewsEvent | None:
        """The most recent event that has already fired."""
        idx = bisect.bisect_left(self._times, now.timestamp())
        for event in reversed(self._events[:idx]):
            if event.impact < min_impact:
                continue
            if symbol and not event.affects(symbol):
                continue
            return event
        return None


class NewsDetector:
    """Cheap per-cycle check for "are we in a news window right now?".

    Args:
        calendar: The event source.
        pre_window: Seconds before a release that count as imminent.
        post_window: Seconds after a release that count as fresh.
        min_impact: Ignore anything below this level.
    """

    def __init__(
        self,
        calendar: EconomicCalendar,
        pre_window: float = 300.0,
        post_window: float = 300.0,
        min_impact: Impact = Impact.HIGH,
    ) -> None:
        self.calendar = calendar
        self.pre_window = pre_window
        self.post_window = post_window
        self.min_impact = min_impact

    def check(self, symbol: str, now: datetime | None = None) -> NewsWindow:
        """Evaluate the news state for one symbol. Safe to call every cycle."""
        now = now or datetime.now(timezone.utc)

        upcoming = self.calendar.next_event(now, self.min_impact, symbol)
        if upcoming is not None:
            gap = upcoming.seconds_until(now)
            if 0 <= gap <= self.pre_window:
                return NewsWindow(upcoming, gap, is_imminent=True, is_fresh=False)

        recent = self.calendar.last_event(now, self.min_impact, symbol)
        if recent is not None:
            since = -recent.seconds_until(now)
            if 0 <= since <= self.post_window:
                return NewsWindow(recent, -since, is_imminent=False, is_fresh=True)

        gap = upcoming.seconds_until(now) if upcoming else float("inf")
        return NewsWindow(upcoming, gap, is_imminent=False, is_fresh=False)

    def just_fired(self, symbol: str, within_seconds: float = 5.0,
                   now: datetime | None = None) -> NewsEvent | None:
        """The fast path: did a qualifying event fire in the last N seconds?

        This is what a react-to-the-release strategy polls on a tight loop. It
        touches one binary search and one comparison, so it can run many times
        a second without loading the process.
        """
        now = now or datetime.now(timezone.utc)
        recent = self.calendar.last_event(now, self.min_impact, symbol)
        if recent is None:
            return None
        elapsed = -recent.seconds_until(now)
        return recent if 0 <= elapsed <= within_seconds else None
