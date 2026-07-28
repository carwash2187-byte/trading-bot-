#!/usr/bin/env python3
"""Write one line a day about what the bot did, so a month away is readable.

Claude cannot watch this account while Leo is gone -- scheduled assistant
sessions expire, and a monitor that silently stops is worse than none. The
answer is not a smarter watcher but a bot that records enough to be understood
after the fact.

So this appends one line per day to `reports/daily.md`: balance, what changed,
how many trades, whether payouts have unlocked, and how close the account is to
the limit that ends it. Coming back to thirty of those lines answers "what
happened" without needing anything to have been watching.

It never trades and never changes anything.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPORT = Path("reports/daily.md")
STATE = Path("run/report_state.json")
QUALIFY_PCT = 0.005          # a payout day is +0.5% on the day
NEEDED_DAYS = 5              # five of them unlock withdrawals
DEATH_PCT = 0.06             # account ends 6% below the STARTING balance


def load(path: Path, default):
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return default


def account_now() -> dict | None:
    """Read the live balance. Returns None if the broker cannot be reached."""
    sys.path.insert(0, str(Path(__file__).parent))
    try:
        from run import load_env
        from tradebot.brokers.base import TradingMode
        from tradebot.brokers.tradelocker import TradeLockerBroker

        env = load_env()
        if not env.get("TRADELOCKER_USERNAME"):
            return None
        broker = TradeLockerBroker(
            username=env["TRADELOCKER_USERNAME"],
            password=env["TRADELOCKER_PASSWORD"],
            server=env["TRADELOCKER_SERVER"],
            account_id=env.get("TRADELOCKER_ACCOUNT", ""),
            mode=TradingMode.DEMO,
        )
        broker.connect()
        snapshot = broker.get_account()
        return {"balance": snapshot.balance, "equity": snapshot.equity,
                "positions": len(broker.get_positions())}
    except Exception:                                          # noqa: BLE001
        # A failed read is itself worth recording; it must not stop the report.
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--public", action="store_true",
        help="omit cash amounts. Set when the report will be committed to a "
             "public repository, where the account balance would otherwise be "
             "readable by anyone. Percentages and payout progress are what "
             "decisions are made on anyway.",
    )
    args = parser.parse_args()
    private = not args.public

    now = datetime.now(timezone.utc)
    today = now.date().isoformat()

    state = load(STATE, {})
    account = account_now()

    starting = state.get("starting_balance")
    if starting is None and account:
        starting = account["balance"]
        state["starting_balance"] = starting

    yesterday = state.get("last_balance")
    qualifying = int(state.get("qualifying_days", 0))
    seen = set(state.get("qualifying_dates", []))

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    if not REPORT.exists():
        REPORT.write_text(
            "# Daily record\n\n"
            "One line a day. `day` is a day that closed +0.5% or better --\n"
            "five of those unlock withdrawals.\n\n"
            "| date | balance | change | day? | payout days | trades | to limit |\n"
            "|---|---|---|---|---|---|---|\n"
        )

    if account is None:
        with REPORT.open("a") as fh:
            fh.write(f"| {today} | — | **could not reach broker** | | | | |\n")
        print(f"{today}: could not reach the broker")
        return 1

    balance = account["balance"]
    change = balance - yesterday if yesterday is not None else 0.0
    change_pct = (change / yesterday * 100) if yesterday else 0.0

    is_qualifying = yesterday and change / yesterday >= QUALIFY_PCT
    if is_qualifying and today not in seen:
        qualifying += 1
        seen.add(today)

    trades = 0
    journal = Path("data/journal.jsonl")
    if journal.exists():
        for line in journal.read_text().splitlines():
            if today in line:
                trades += 1

    death_line = starting * (1 - DEATH_PCT) if starting else 0
    room = balance - death_line
    room_pct = (room / starting * 100) if starting else 0

    unlocked = "UNLOCKED" if qualifying >= NEEDED_DAYS else f"{qualifying}/{NEEDED_DAYS}"
    mark = "yes" if is_qualifying else ""

    shown_balance = f"${balance:,.2f}" if private else "—"
    shown_change = (f"{change:+,.2f} ({change_pct:+.2f}%)" if private
                    else f"{change_pct:+.2f}%")
    shown_room = (f"${room:,.0f} ({room_pct:.1f}%)" if private
                  else f"{room_pct:.1f}%")

    with REPORT.open("a") as fh:
        fh.write(
            f"| {today} | {shown_balance} | {shown_change} | "
            f"{mark} | {unlocked} | {trades} | {shown_room} |\n"
        )

    state.update({
        "last_balance": balance,
        "qualifying_days": qualifying,
        "qualifying_dates": sorted(seen),
        "updated": now.isoformat(),
    })
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, indent=2))

    if private:
        print(f"{today}: ${balance:,.2f} ({change:+,.2f}), "
              f"payout days {unlocked}, ${room:,.0f} above the limit")
    else:
        print(f"{today}: {change_pct:+.2f}%, payout days {unlocked}, "
              f"{room_pct:.1f}% above the limit")
    return 0


if __name__ == "__main__":
    sys.exit(main())
