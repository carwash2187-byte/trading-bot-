#!/usr/bin/env python3
"""Tell Leo when the bot breaks, without him having to check.

The watchdog restarts a dead job and doctor.py reports health, but both are
silent unless someone goes looking. A bot that quietly stopped a fortnight ago
has cost two weeks of trading, and the only signal was an absence -- nothing
happened, and nothing said so.

This runs on its own schedule and raises a macOS notification when something is
actually wrong. It stays quiet when everything is fine, because an alert that
fires every hour gets ignored within a day and then the one that matters is
ignored too.

It never trades and never changes anything.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

STATE = Path("run/alert.json")

# Do not repeat the same complaint more often than this. The failure is
# usually not fixed within the hour, and repeating it teaches you to swipe
# notifications away without reading them.
QUIET_HOURS = 6


def notify(title: str, message: str) -> None:
    """Raise a macOS notification. Falls back to printing if that fails."""
    try:
        subprocess.run(
            ["osascript", "-e",
             f'display notification {json.dumps(message)} '
             f'with title {json.dumps(title)} sound name "Basso"'],
            capture_output=True, timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        pass
    print(f"{title}: {message}")


def recently_warned(key: str) -> bool:
    """Has this exact problem already been reported in the quiet window?"""
    try:
        seen = json.loads(STATE.read_text())
    except (OSError, json.JSONDecodeError):
        return False
    raw = seen.get(key)
    if not raw:
        return False
    try:
        when = datetime.fromisoformat(raw)
    except ValueError:
        return False
    return datetime.now(timezone.utc) - when < timedelta(hours=QUIET_HOURS)


def remember(key: str) -> None:
    try:
        seen = json.loads(STATE.read_text())
    except (OSError, json.JSONDecodeError):
        seen = {}
    seen[key] = datetime.now(timezone.utc).isoformat()
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(seen, indent=2))


def main() -> int:
    problems: list[tuple[str, str]] = []

    heartbeat = Path("run/heartbeat.json")
    try:
        beat = json.loads(heartbeat.read_text())
        last = datetime.fromisoformat(str(beat["last_beat"]))
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        minutes = (datetime.now(timezone.utc) - last).total_seconds() / 60
        if minutes > 30:
            problems.append((
                "stopped",
                f"The bot has not run for {minutes:.0f} minutes. "
                f"It should run every 5. It is not trading.",
            ))
    except (OSError, json.JSONDecodeError, KeyError, ValueError):
        problems.append(("no-heartbeat",
                         "The bot has never run, or its heartbeat file is broken."))

    # An account that has stopped being able to trade is worth knowing about
    # immediately -- it looks identical to a quiet market from the outside.
    try:
        portfolio = json.loads(Path("run/portfolio.json").read_text())
        slots = portfolio.get("strategies") or portfolio.get("slots") or {}
        if slots:
            active = [n for n, s in slots.items()
                      if (s.get("status") if isinstance(s, dict) else s) == "active"]
            if not active:
                problems.append((
                    "all-benched",
                    "Every strategy has been benched for losing. The bot is "
                    "running but cannot place a trade.",
                ))
    except (OSError, json.JSONDecodeError):
        pass

    # A drawdown approaching the prop firm's cap is the one number worth
    # interrupting someone for. Past it the account is gone, not recoverable.
    try:
        risk = json.loads(Path("run/risk.json").read_text())
        drawdown = float(risk.get("drawdown_pct", 0))
        if drawdown >= 4.0:
            problems.append((
                "near-cap",
                f"Down {drawdown:.1f}% from the peak. The account dies at 6%.",
            ))
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        pass

    fresh = [(k, m) for k, m in problems if not recently_warned(k)]
    for key, message in fresh:
        notify("Trading bot problem", message)
        remember(key)

    if not problems:
        print("all clear")
        return 0

    if not fresh:
        print(f"{len(problems)} problem(s), already reported recently — staying quiet")
    return 1


if __name__ == "__main__":
    sys.exit(main())
