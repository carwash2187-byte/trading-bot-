"""Single-instance lock.

Two copies of the bot against one account is the worst failure in the whole
system: both read the same state, both decide to enter, and the account ends up
with double the intended size while the journal records half of it. Nothing
else in this package can detect that after the fact, so it is prevented here.

Uses an OS-level advisory lock (``fcntl`` on POSIX, ``msvcrt`` on Windows)
rather than a "does the pid file exist" check. A lock held by the kernel is
released automatically when the process dies, so a hard kill or an OOM does not
leave a stale file that blocks the next start.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import TracebackType

if sys.platform == "win32":  # pragma: no cover - platform-specific
    import msvcrt
else:
    import fcntl


class AlreadyRunning(RuntimeError):
    """Raised when another instance already holds the lock."""


class InstanceLock:
    """Exclusive, non-blocking lock scoped to a lock-file path.

    Usage::

        with InstanceLock("run/bot.lock"):
            run_cycle()

    Acquiring raises :class:`AlreadyRunning` immediately rather than waiting —
    a scheduled job that overlaps its predecessor should skip this run, not
    queue up behind it.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = None

    def acquire(self) -> "InstanceLock":
        self._fh = self.path.open("a+", encoding="utf-8")
        try:
            if sys.platform == "win32":  # pragma: no cover
                msvcrt.locking(self._fh.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                fcntl.flock(self._fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            holder = self._read_holder()
            self._fh.close()
            self._fh = None
            raise AlreadyRunning(
                f"another instance holds {self.path} ({holder}); skipping this run"
            ) from None

        # Record who holds it — purely informational, the lock is the real gate.
        self._fh.seek(0)
        self._fh.truncate()
        self._fh.write(
            f"pid={os.getpid()} host={os.uname().nodename if hasattr(os, 'uname') else '?'} "
            f"since={datetime.now(timezone.utc).isoformat()}\n"
        )
        self._fh.flush()
        return self

    def release(self) -> None:
        if self._fh is None:
            return
        try:
            if sys.platform == "win32":  # pragma: no cover
                self._fh.seek(0)
                msvcrt.locking(self._fh.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(self._fh.fileno(), fcntl.LOCK_UN)
        except OSError:
            pass
        finally:
            self._fh.close()
            self._fh = None

    def _read_holder(self) -> str:
        try:
            return self.path.read_text(encoding="utf-8").strip() or "unknown holder"
        except OSError:
            return "unknown holder"

    @property
    def held(self) -> bool:
        return self._fh is not None

    def __enter__(self) -> "InstanceLock":
        return self.acquire()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.release()
