"""Watchdog: makes sure the scheduled job is actually still firing.

The main bot runs as a short-lived scheduled job. That is robust against
memory leaks and wedged sockets, but it has one failure mode: the *scheduler*
stops firing and nothing notices, because a job that never runs also never
errors.

So every successful cycle writes a heartbeat, and this watchdog — run on its
own, slower schedule — checks how old that heartbeat is. If it has gone stale,
it raises an alert and can relaunch the job.

Run the watchdog from a different mechanism than the bot itself. A watchdog
started by the same cron that died is not a watchdog.
"""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .state import StateStore

log = logging.getLogger("tradebot.watchdog")


@dataclass
class HeartbeatStatus:
    """How healthy the main job looks right now."""

    last_beat: datetime | None
    age_seconds: float
    stale: bool
    healthy: bool
    detail: str

    def describe(self) -> str:
        if self.last_beat is None:
            return "no heartbeat ever recorded"
        return f"last beat {self.age_seconds:.0f}s ago ({self.detail})"


class Heartbeat:
    """Written by the bot, read by the watchdog."""

    def __init__(self, path: str | Path = "run/heartbeat.json") -> None:
        self.store = StateStore(path, defaults={"last_beat": None, "cycles": 0, "ok": True})

    def beat(self, ok: bool = True, note: str = "") -> None:
        """Record a completed cycle. Call once per successful pass."""
        current = self.store.load().data
        self.store.save(
            {
                "last_beat": datetime.now(timezone.utc).isoformat(),
                "cycles": int(current.get("cycles", 0)) + 1,
                "ok": ok,
                "note": note,
            }
        )

    def status(self, max_age: timedelta, now: datetime | None = None) -> HeartbeatStatus:
        now = now or datetime.now(timezone.utc)
        data = self.store.load().data
        raw = data.get("last_beat")
        if not raw:
            return HeartbeatStatus(None, float("inf"), True, False, "never started")

        try:
            last = datetime.fromisoformat(str(raw))
            if last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
        except ValueError:
            return HeartbeatStatus(None, float("inf"), True, False, "unparseable timestamp")

        age = (now - last).total_seconds()
        stale = age > max_age.total_seconds()
        ok_flag = bool(data.get("ok", True))
        return HeartbeatStatus(
            last_beat=last,
            age_seconds=age,
            stale=stale,
            healthy=not stale and ok_flag,
            detail="stale" if stale else ("last cycle reported errors" if not ok_flag else "fresh"),
        )


class Watchdog:
    """Checks the heartbeat and optionally relaunches the job.

    Args:
        heartbeat: The shared heartbeat file.
        max_age: How old the last beat may get before it counts as stale.
            Set this to a comfortable multiple of the job's interval — a single
            missed run on a busy machine is not an emergency.
        restart_command: Argv to run when stale. Omit to alert only.
    """

    def __init__(
        self,
        heartbeat: Heartbeat,
        max_age: timedelta = timedelta(minutes=15),
        restart_command: list[str] | None = None,
        max_restarts_per_hour: int = 4,
        state_path: str | Path = "run/watchdog.json",
    ) -> None:
        self.heartbeat = heartbeat
        self.max_age = max_age
        self.restart_command = restart_command
        self.max_restarts_per_hour = max_restarts_per_hour
        self.store = StateStore(state_path, defaults={"restarts": []})

    def check(self, now: datetime | None = None) -> HeartbeatStatus:
        """Evaluate health and act if the job has gone stale."""
        now = now or datetime.now(timezone.utc)
        status = self.heartbeat.status(self.max_age, now)

        if not status.stale:
            log.debug("watchdog: %s", status.describe())
            return status

        log.error("watchdog: main job looks dead — %s", status.describe())
        if self.restart_command and self._may_restart(now):
            self._restart(now)
        return status

    def _may_restart(self, now: datetime) -> bool:
        """Rate-limit restarts so a crash loop does not become a fork bomb."""
        recent = self._recent_restarts(now)
        if len(recent) >= self.max_restarts_per_hour:
            log.critical(
                "watchdog: %d restarts in the last hour, refusing to restart again. "
                "Something is broken that restarting will not fix.",
                len(recent),
            )
            return False
        return True

    def _recent_restarts(self, now: datetime) -> list[str]:
        raw = self.store.load().data.get("restarts", [])
        cutoff = now - timedelta(hours=1)
        out = []
        for stamp in raw:
            try:
                ts = datetime.fromisoformat(str(stamp))
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                if ts >= cutoff:
                    out.append(stamp)
            except ValueError:
                continue
        return out

    def _restart(self, now: datetime) -> None:
        log.warning("watchdog: restarting via %s", " ".join(self.restart_command or []))
        try:
            subprocess.Popen(
                self.restart_command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,   # survive the watchdog exiting
            )
        except OSError as err:
            log.critical("watchdog: restart failed: %s", err)
            return
        history = self._recent_restarts(now)
        history.append(now.isoformat())
        self.store.save({"restarts": history})
