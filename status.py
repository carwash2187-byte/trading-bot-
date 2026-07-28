#!/usr/bin/env python3
"""Everything about the bot in one screen: cloud, account, and trades.

`doctor.py` checks a bot running on this machine. This one checks the bot that
is actually trading -- which now lives on GitHub -- and the account it trades.
Both are needed, because the two ways this fails look nothing alike: the cloud
job can stop running, or it can run perfectly and place nothing.

Read-only. It cannot trade, cancel, or change anything.

    python3 status.py                  # cloud + account
    python3 status.py --token ghp_...  # include the GitHub side
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO = "carwash2187-byte/trading-bot-"


def github(path: str, token: str) -> dict | None:
    request = urllib.request.Request(
        f"https://api.github.com/repos/{REPO}/{path}",
        headers={"Authorization": f"Bearer {token}",
                 "Accept": "application/vnd.github+json",
                 "User-Agent": "tradebot-status"},
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode())
    except (urllib.error.URLError, urllib.error.HTTPError, OSError):
        return None


def show_cloud(token: str) -> None:
    print("THE BOT (running on GitHub)")

    runs = github("actions/runs?per_page=20", token)
    if runs is None:
        print("  could not reach GitHub. Check the token, or look at")
        print(f"  https://github.com/{REPO}/actions")
        return

    trades = [r for r in runs.get("workflow_runs", []) if r["name"] == "trade"]
    if not trades:
        print("  no runs yet")
        return

    newest = trades[0]
    when = datetime.fromisoformat(newest["created_at"].replace("Z", "+00:00"))
    age = (datetime.now(timezone.utc) - when).total_seconds() / 60

    failed = sum(1 for r in trades if r["conclusion"] == "failure")
    print(f"  last check   {age:.0f} minutes ago "
          f"({'OK' if newest['conclusion'] == 'success' else 'FAILED'})")
    print(f"  last {len(trades)} runs  {len(trades) - failed} fine, {failed} failed")

    # More than an occasional failure means it is not really trading, even
    # though the schedule looks alive.
    if age > 20:
        print("  ** it has not run recently. Something has stopped it. **")

    # Only judge the failure rate once there is a rate to judge. One failure
    # out of three is noise -- and right after a fix, the run that prompted the
    # fix is still in the window. A warning that fires on noise gets ignored,
    # and then the real one gets ignored too.
    if len(trades) >= 10 and failed > len(trades) / 4:
        print("  ** failing often. Open the Actions tab and read the error. **")
    elif failed and len(trades) < 10:
        print(f"  ({failed} early failure(s) — normal while settling in)")


def show_account() -> None:
    print("\nTHE ACCOUNT")
    sys.path.insert(0, str(Path(__file__).parent))
    try:
        from run import load_env
        from tradebot.brokers.base import TradingMode
        from tradebot.brokers.tradelocker import TradeLockerBroker

        env = load_env()
        if not env.get("TRADELOCKER_USERNAME"):
            print("  no credentials on this machine (they live in GitHub Secrets)")
            return

        broker = TradeLockerBroker(
            username=env["TRADELOCKER_USERNAME"],
            password=env["TRADELOCKER_PASSWORD"],
            server=env["TRADELOCKER_SERVER"],
            account_id=env.get("TRADELOCKER_ACCOUNT", ""),
            mode=TradingMode.DEMO,
        )
        broker.connect()
        account = broker.get_account()
        positions = broker.get_positions()

        print(f"  balance      ${account.balance:,.2f}")
        print(f"  equity       ${account.equity:,.2f}   "
              f"({'includes open trades' if positions else 'nothing open'})")

        state = Path("run/report_state.json")
        started = None
        if state.exists():
            started = json.loads(state.read_text()).get("starting_balance")
        started = started or account.balance

        # The 6% is measured from the starting balance, not the peak.
        floor = started * 0.94
        room = account.equity - floor
        print(f"  account ends at ${floor:,.2f} -- ${room:,.0f} of room "
              f"({room / started * 100:.1f}%)")

        if positions:
            print(f"\n  {len(positions)} open:")
            for p in positions:
                print(f"    {p.side.value} {p.lots} {p.symbol} from "
                      f"{p.entry_price:,.2f}, stop {p.stop_loss:,.2f}, "
                      f"P&L ${p.unrealized_pnl:+,.2f}")
        else:
            print("\n  nothing open. Normal -- it trades about 4-5 times a week.")

    except Exception as exc:                                   # noqa: BLE001
        print(f"  could not read the account: {exc}")


def show_trades() -> None:
    print("\nTRADES SO FAR")
    journal = Path("data/journal.jsonl")
    rows = []
    if journal.exists():
        for line in journal.read_text().splitlines():
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    if not rows:
        print("  none closed yet.")
        print("  (the record lives in the repo: reports/daily.md)")
        return

    wins = [r for r in rows if r.get("realized_pnl", 0) > 0]
    total = sum(r.get("realized_pnl", 0) for r in rows)
    print(f"  {len(rows)} closed, {len(wins)} won "
          f"({100 * len(wins) / len(rows):.0f}%), net ${total:+,.2f}")
    for row in rows[-5:]:
        print(f"    {row.get('closed_at', '')[:16]}  {row.get('symbol')} "
              f"${row.get('realized_pnl', 0):+,.2f}  {row.get('reason', '')}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Check on the bot.")
    parser.add_argument("--token", default=os.environ.get("GITHUB_TOKEN", ""),
                        help="a GitHub token, to read the cloud runs")
    args = parser.parse_args()

    print()
    if args.token:
        show_cloud(args.token)
    else:
        print("THE BOT (running on GitHub)")
        print(f"  no token given -- check by eye at")
        print(f"  https://github.com/{REPO}/actions")

    show_account()
    show_trades()
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
