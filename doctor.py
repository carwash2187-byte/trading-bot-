#!/usr/bin/env python3
"""Tell me, in plain English, whether the bot is actually working.

The existing watchdog catches a bot that has *stopped*. It cannot catch the
failure that costs more, because that one looks identical to success from the
outside: the job fires on schedule, writes a healthy heartbeat, logs no errors,
and quietly never places a trade. Every green light is on and the account does
nothing for a month.

That happens for boring reasons -- the portfolio manager benched every strategy,
an instrument stopped resolving, the price feed returns too few bars to warm an
indicator, credentials expired into a read-only session. None of them raise.

So this checks the things that are only wrong in combination, and says so in
words rather than status codes. It never trades and never writes; it is safe to
run at any time, including while the bot is mid-cycle.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

OK = "ok"
WARN = "warn"
BAD = "bad"

MARK = {OK: "[ ok ]", WARN: "[warn]", BAD: "[BAD ]"}


@dataclass
class Check:
    """One question, its answer, and what to do about it."""

    level: str
    title: str
    detail: str
    fix: str = ""

    def render(self) -> str:
        out = f"{MARK[self.level]} {self.title}\n       {self.detail}"
        if self.fix and self.level != OK:
            out += f"\n       -> {self.fix}"
        return out


def _load(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def check_heartbeat(run_dir: Path, max_age_minutes: int) -> Check:
    """Is the scheduler still firing the job at all?"""
    data = _load(run_dir / "heartbeat.json")
    raw = data.get("last_beat")
    if not raw:
        return Check(
            BAD, "Is it running?",
            "The bot has never completed a single cycle.",
            "Start it: python3 run.py --broker paper --strategies big_runner",
        )
    try:
        last = datetime.fromisoformat(str(raw))
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
    except ValueError:
        return Check(BAD, "Is it running?", "The heartbeat file is corrupt.",
                     "Delete run/heartbeat.json and restart the bot.")

    age = (datetime.now(timezone.utc) - last).total_seconds() / 60
    cycles = data.get("cycles", 0)
    if age > max_age_minutes:
        return Check(
            BAD, "Is it running?",
            f"Last ran {age:.0f} minutes ago. It should run every few minutes. "
            f"It has stopped.",
            "Check the schedule is loaded: launchctl list | grep tradebot",
        )
    if not data.get("ok", True):
        return Check(
            WARN, "Is it running?",
            f"Running ({cycles:,} cycles), but the last one reported errors: "
            f"{data.get('note', 'no detail')}",
            "Look at the log for the failing symbol or broker call.",
        )
    return Check(OK, "Is it running?",
                 f"Yes. Last ran {age:.1f} minutes ago, {cycles:,} cycles total.")


def check_strategies(run_dir: Path) -> Check:
    """Is anything actually allowed to trade?

    The portfolio manager benches strategies that stop working. If it benches
    the last one, the bot keeps running perfectly and can never open a trade.
    """
    data = _load(run_dir / "portfolio.json")
    slots = data.get("strategies") or data.get("slots") or {}
    if not slots:
        return Check(WARN, "Can it trade?",
                     "No strategy record yet -- it has not completed a review.",
                     "Normal on a fresh install. Recheck after it has run a while.")

    active = [n for n, s in slots.items()
              if (s.get("status") if isinstance(s, dict) else s) == "active"]
    benched = [n for n in slots if n not in active]

    if not active:
        return Check(
            BAD, "Can it trade?",
            f"No. All {len(slots)} strategies are benched ({', '.join(benched)}). "
            f"The bot is running but cannot open a trade.",
            "The manager benched them for losing. Do not just re-enable them -- "
            "backtest first: python3 sweep.py",
        )
    note = f"Yes. Active: {', '.join(active)}."
    if benched:
        note += f" Benched for losing: {', '.join(benched)}."
    return Check(OK, "Can it trade?", note)


def check_trading(journal: Path, quiet_days: float) -> Check:
    """Has it actually done anything lately?

    A bot that is alive, unbenched, and still silent for weeks is the case
    worth catching -- nothing else reports it.
    """
    if not journal.exists():
        return Check(WARN, "Has it traded?",
                     "No trade log yet. It has not closed a trade.",
                     "Expected on a new install or a slow strategy.")

    stamps = []
    for line in journal.read_text().splitlines():
        try:
            row = json.loads(line)
            stamps.append(datetime.fromisoformat(row["closed_at"]))
        except (json.JSONDecodeError, KeyError, ValueError):
            continue
    if not stamps:
        return Check(WARN, "Has it traded?", "The trade log is empty.")

    last = max(stamps)
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    days = (datetime.now(timezone.utc) - last).total_seconds() / 86400

    if days > quiet_days:
        return Check(
            WARN, "Has it traded?",
            f"{len(stamps)} trades total, but nothing for {days:.0f} days. "
            f"The Big-Runner only trades every 5 days or so, but {days:.0f} is "
            f"long even for it.",
            "Check the price feed is returning enough bars to warm the "
            "indicators, and that the symbol still resolves.",
        )
    return Check(OK, "Has it traded?",
                 f"Yes. {len(stamps)} trades, most recent {days:.1f} days ago.")


def check_schedule() -> Check:
    """Is the thing that starts the bot still installed?"""
    try:
        out = subprocess.run(["launchctl", "list"], capture_output=True,
                             text=True, timeout=10).stdout
    except (OSError, subprocess.SubprocessError):
        return Check(WARN, "Is the schedule installed?",
                     "Could not ask launchctl.")

    rows = [l for l in out.splitlines() if "tradebot" in l.lower()]
    if not rows:
        return Check(
            BAD, "Is the schedule installed?",
            "No tradebot job is loaded. Nothing will start the bot.",
            "launchctl load ~/Library/LaunchAgents/com.tradebot.plist",
        )
    # Column 2 is the last exit status; non-zero means the job is crashing.
    for row in rows:
        parts = row.split()
        if len(parts) >= 2 and parts[1] not in ("0", "-"):
            return Check(
                BAD, "Is the schedule installed?",
                f"Loaded, but the last run exited with status {parts[1]} -- "
                f"it is crashing on startup.",
                "Run it by hand to see the error: python3 run.py --verbose",
            )
    return Check(OK, "Is the schedule installed?",
                 f"Yes, and its last run exited cleanly.")


def check_live_guard() -> Check:
    """Is anything pointed at real money by accident?"""
    import os

    if os.environ.get("TRADEBOT_ALLOW_LIVE"):
        return Check(
            WARN, "Real money?",
            "TRADEBOT_ALLOW_LIVE is set. Live orders are permitted.",
            "If you did not mean that, unset it before the next run.",
        )
    return Check(OK, "Real money?",
                 "No. The live guard is off, so it cannot place a real order.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Check the bot's health.")
    parser.add_argument("--run-dir", default="run")
    parser.add_argument("--journal", default="data/journal.jsonl")
    parser.add_argument("--max-age-minutes", type=int, default=30,
                        help="how stale the heartbeat may get before it is dead")
    parser.add_argument("--quiet-days", type=float, default=14.0,
                        help="how long without a trade before that is suspicious")
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    checks = [
        check_heartbeat(run_dir, args.max_age_minutes),
        check_schedule(),
        check_strategies(run_dir),
        check_trading(Path(args.journal), args.quiet_days),
        check_live_guard(),
    ]

    print()
    for check in checks:
        print(check.render())
        print()

    bad = [c for c in checks if c.level == BAD]
    warn = [c for c in checks if c.level == WARN]

    if bad:
        print(f"VERDICT: something is broken. {len(bad)} problem(s) above "
              f"need fixing before it will make money.")
    elif warn:
        print(f"VERDICT: running, but {len(warn)} thing(s) worth a look.")
    else:
        print("VERDICT: healthy. It is running, allowed to trade, and trading.")
    print()

    raise SystemExit(1 if bad else 0)


if __name__ == "__main__":
    main()
