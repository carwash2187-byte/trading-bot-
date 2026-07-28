"""Self-healing persistent state.

State is written atomically: serialise to a temp file, fsync, then rename over
the real one. A rename on the same filesystem is atomic, so a crash mid-write
leaves the previous good file intact rather than a truncated one.

On load, a corrupted file is moved aside with a timestamped ``.corrupt``
suffix and the caller gets defaults instead of an exception. Losing state and
carrying on beats a crash loop, and the bad file is preserved for inspection.
"""

from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class StateLoadResult:
    """What happened during a load, so callers can log it."""

    data: dict[str, Any]
    recovered: bool = False        # True if a corrupt file was quarantined
    backup_path: Path | None = None


class StateStore:
    """Atomic, corruption-tolerant JSON state on disk."""

    def __init__(self, path: str | Path, defaults: dict[str, Any] | None = None) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.defaults = defaults or {}

    def load(self) -> StateLoadResult:
        """Read state, quarantining and replacing the file if it is unusable."""
        if not self.path.exists():
            return StateLoadResult(dict(self.defaults))

        try:
            raw = self.path.read_text(encoding="utf-8")
            data = json.loads(raw)
            if not isinstance(data, dict):
                raise ValueError("state root must be a JSON object")
            merged = dict(self.defaults)
            merged.update(data)
            return StateLoadResult(merged)
        except (json.JSONDecodeError, ValueError, OSError, UnicodeDecodeError):
            backup = self._quarantine()
            return StateLoadResult(dict(self.defaults), recovered=True, backup_path=backup)

    def save(self, data: dict[str, Any]) -> None:
        """Write state atomically. Either the whole update lands, or none of it."""
        payload = dict(data)
        payload["_saved_at"] = datetime.now(timezone.utc).isoformat()

        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, default=str)
            fh.flush()
            os.fsync(fh.fileno())        # survive a power cut, not just a crash
        tmp.replace(self.path)

    def update(self, **changes: Any) -> dict[str, Any]:
        """Read-modify-write a few keys."""
        current = self.load().data
        current.update(changes)
        self.save(current)
        return current

    def _quarantine(self) -> Path | None:
        """Move a bad state file aside so the next start is clean."""
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup = self.path.with_suffix(self.path.suffix + f".corrupt.{stamp}")
        try:
            shutil.move(str(self.path), str(backup))
            return backup
        except OSError:
            try:
                self.path.unlink()      # last resort: at least unblock startup
            except OSError:
                pass
            return None
