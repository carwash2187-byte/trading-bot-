#!/usr/bin/env python3
"""Notice when the cloud bot has gone quiet, and say so out loud.

The bot trades from GitHub Actions. Every failure mode ON the runner is
handled there -- retries, the heal workflow, the issue that emails Leo. What
none of that can catch is GitHub not starting runs at all: a schedule that
never fires produces no failed run, no issue, no email. It produces nothing,
which is the point of this watcher.

It asks GitHub's public API (the repo is public, so no token lives on this
machine) when the last trade run happened, and raises a macOS notification if
that is too long ago. It runs on Leo's laptop whenever the laptop is awake --
a bounded promise on purpose. A watcher that only helps when the machine is on
is still strictly better than the silence it replaces, and it holds no
credentials and places no trades, so it cannot double an order no matter how
wrong it goes.
"""

from __future__ import annotations

import json
import subprocess
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = "carwash2187-byte/trading-bot-"
QUIET_MINUTES = 30          # six missed five-minute slots is a stopped bot
STATE = Path("run/cloudwatch.json")


def notify(message: str) -> None:
    try:
        subprocess.run(
            ["osascript", "-e",
             f'display notification {json.dumps(message)} '
             f'with title "Cloud trading bot" sound name "Basso"'],
            capture_output=True, timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        pass
    print(message)


def recently_warned() -> bool:
    try:
        stamp = datetime.fromisoformat(json.loads(STATE.read_text())["warned"])
    except (OSError, json.JSONDecodeError, KeyError, ValueError):
        return False
    return datetime.now(timezone.utc) - stamp < timedelta(hours=6)


def remember_warning() -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(
        {"warned": datetime.now(timezone.utc).isoformat()}))


def main() -> int:
    url = (f"https://api.github.com/repos/{REPO}/actions/runs"
           f"?per_page=10&status=completed")
    request = urllib.request.Request(
        url, headers={"User-Agent": "tradebot-cloudwatch",
                      "Accept": "application/vnd.github+json"})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            runs = json.loads(response.read().decode()).get("workflow_runs", [])
    except Exception:                                          # noqa: BLE001
        # No internet here says nothing about the bot; GitHub is still running
        # it. Stay quiet rather than cry wolf from a coffee-shop dropout.
        print("could not reach GitHub; saying nothing")
        return 0

    trades = [r for r in runs if r["name"] == "trade"]
    if not trades:
        if not recently_warned():
            notify("The cloud bot has never run. Open the repo's Actions tab.")
            remember_warning()
        return 1

    newest = datetime.fromisoformat(
        trades[0]["created_at"].replace("Z", "+00:00"))
    age = (datetime.now(timezone.utc) - newest).total_seconds() / 60

    if age > QUIET_MINUTES:
        if not recently_warned():
            notify(f"The cloud bot has not traded a cycle in {age:.0f} minutes. "
                   f"It should run every 5. Check the Actions tab.")
            remember_warning()
        return 1

    print(f"cloud bot fine: last run {age:.0f} minutes ago")
    return 0


if __name__ == "__main__":
    sys.exit(main())
