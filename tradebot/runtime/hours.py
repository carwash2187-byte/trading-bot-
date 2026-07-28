"""Market hours per instrument class.

Outside session hours the bot does nothing — it returns "closed" and the cycle
ends cleanly. That is different from erroring out: a scheduled job that raises
every five minutes all weekend fills the logs with noise and trains you to
ignore alerts.

All reasoning is in UTC. Sessions are expressed in the venue's local time and
converted, so daylight-saving shifts are handled by the timezone database
rather than by hand-tuned offsets.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover - Python < 3.9
    ZoneInfo = None  # type: ignore[assignment]


@dataclass(frozen=True)
class SessionStatus:
    """Whether a market is open, and when that changes next."""

    is_open: bool
    reason: str
    next_change: datetime | None = None

    def __bool__(self) -> bool:
        return self.is_open


class MarketSchedule:
    """Base class. Subclasses answer :meth:`status` for one venue type."""

    name = "generic"

    def status(self, now: datetime | None = None) -> SessionStatus:
        raise NotImplementedError

    def is_open(self, now: datetime | None = None) -> bool:
        return self.status(now).is_open


class ForexSchedule(MarketSchedule):
    """24/5: opens Sunday evening, closes Friday evening, New York time.

    Defaults to the usual 17:00 New York open/close. Also skips the daily
    rollover window, when spreads blow out and liquidity thins.
    """

    name = "forex"

    def __init__(
        self,
        open_weekday: int = 6,          # Sunday
        open_hour: int = 17,
        close_weekday: int = 4,         # Friday
        close_hour: int = 17,
        tz: str = "America/New_York",
        skip_rollover: bool = True,
        rollover_start: time = time(16, 55),
        rollover_end: time = time(17, 5),
    ) -> None:
        self.open_weekday = open_weekday
        self.open_hour = open_hour
        self.close_weekday = close_weekday
        self.close_hour = close_hour
        self.tz = ZoneInfo(tz) if ZoneInfo else timezone.utc
        self.skip_rollover = skip_rollover
        self.rollover_start = rollover_start
        self.rollover_end = rollover_end

    def status(self, now: datetime | None = None) -> SessionStatus:
        now = (now or datetime.now(timezone.utc)).astimezone(self.tz)
        weekday = now.weekday()          # Monday=0 .. Sunday=6

        if weekday == 5:                 # Saturday, always shut
            return SessionStatus(False, "weekend (Saturday)")
        if weekday == self.open_weekday and now.hour < self.open_hour:
            return SessionStatus(False, "weekend (before Sunday open)")
        if weekday == self.close_weekday and now.hour >= self.close_hour:
            return SessionStatus(False, "weekend (after Friday close)")

        if self.skip_rollover and self.rollover_start <= now.time() <= self.rollover_end:
            return SessionStatus(False, "daily rollover (wide spreads)")

        return SessionStatus(True, "open")


class ExchangeSchedule(MarketSchedule):
    """Fixed daily session on weekdays — equities, index futures, and similar."""

    name = "exchange"

    def __init__(
        self,
        open_time: time = time(9, 30),
        close_time: time = time(16, 0),
        tz: str = "America/New_York",
        holidays: set[str] | None = None,
    ) -> None:
        self.open_time = open_time
        self.close_time = close_time
        self.tz = ZoneInfo(tz) if ZoneInfo else timezone.utc
        self.holidays = holidays or set()

    def status(self, now: datetime | None = None) -> SessionStatus:
        now = (now or datetime.now(timezone.utc)).astimezone(self.tz)
        if now.weekday() >= 5:
            return SessionStatus(False, "weekend")
        if now.date().isoformat() in self.holidays:
            return SessionStatus(False, "exchange holiday")
        if not (self.open_time <= now.time() < self.close_time):
            return SessionStatus(False, "outside session hours")
        return SessionStatus(True, "open")


class AlwaysOpenSchedule(MarketSchedule):
    """Crypto and anything else that genuinely never closes."""

    name = "always"

    def status(self, now: datetime | None = None) -> SessionStatus:
        return SessionStatus(True, "24/7 market")


# Map a symbol to its schedule. Extend as instruments are added.
SCHEDULES: dict[str, MarketSchedule] = {
    "EURUSD": ForexSchedule(),
    "GBPUSD": ForexSchedule(),
    "USDJPY": ForexSchedule(),
    "XAUUSD": ForexSchedule(),
    "BTCUSD": AlwaysOpenSchedule(),
}

DEFAULT_SCHEDULE = ForexSchedule()


def schedule_for(symbol: str) -> MarketSchedule:
    return SCHEDULES.get(symbol.upper(), DEFAULT_SCHEDULE)


def is_tradable(symbol: str, now: datetime | None = None) -> SessionStatus:
    """Convenience wrapper used by the trading cycle."""
    return schedule_for(symbol).status(now)
