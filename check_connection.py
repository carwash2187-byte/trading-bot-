#!/usr/bin/env python3
"""Check the broker login works, and nothing else.

Deliberately incapable of trading: it logs in, reads the account, and reads a
price. There is no order code in this file, so it can be run on a real funded
account without any possibility of placing a trade by accident.

It exists because the first connection to a live broker always fails on
something small -- a server name that is not quite right, a symbol the firm
calls XAUUSD.x, an account number from the wrong tab -- and finding that out
while the trading loop is also running makes it far harder to see which part
broke.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

OK = "  OK   "
BAD = " FAILED"


def load_env(path: str = ".env") -> dict:
    """Read the .env file without needing any extra package installed."""
    values = {}
    env_path = Path(path)
    if not env_path.exists():
        return values
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        # Strip quotes people add out of habit; they become part of the
        # password otherwise and the failure looks like a wrong password.
        values[key.strip()] = value.strip().strip("'\"")
    return values


def main() -> int:
    print()
    settings = load_env()
    for key, value in settings.items():
        os.environ.setdefault(key, value)

    # The account number is deliberately not required. The adapter asks the
    # broker which accounts the login owns and takes the first one, so making
    # it mandatory would only be one more thing to look up and get wrong.
    needed = ["TRADELOCKER_USERNAME", "TRADELOCKER_PASSWORD",
              "TRADELOCKER_SERVER"]
    missing = [k for k in needed if not os.environ.get(k)]

    if not Path(".env").exists():
        print(f"{BAD}  No .env file found.")
        print("         Run:  cp .env.example .env && open -e .env")
        # Only three values are asked for; the account number is discovered.
        print("         Then fill in your email, password and server name.")
        print()
        return 1

    if missing:
        print(f"{BAD}  These are empty in your .env file:")
        for key in missing:
            print(f"           {key}")
        print("         Open it with:  open -e ~/tradebot/.env")
        print()
        return 1

    chosen_account = os.environ.get("TRADELOCKER_ACCOUNT", "")
    print(f"{OK}  Found your login in .env")
    print(f"         user    {os.environ['TRADELOCKER_USERNAME']}")
    print(f"         server  {os.environ['TRADELOCKER_SERVER']}")
    print(f"         account {chosen_account or '(not set - will use the first one)'}")
    print()

    try:
        from tradebot.brokers.base import BrokerError, TradingMode
        from tradebot.brokers.tradelocker import TradeLockerBroker
    except ImportError as exc:
        print(f"{BAD}  Could not load the broker code: {exc}")
        print()
        return 1

    broker = TradeLockerBroker(
        username=os.environ["TRADELOCKER_USERNAME"],
        password=os.environ["TRADELOCKER_PASSWORD"],
        server=os.environ["TRADELOCKER_SERVER"],
        account_id=chosen_account,
        mode=TradingMode.DEMO,      # funded accounts report as demo
    )

    try:
        broker.connect()
    except BrokerError as exc:
        print(f"{BAD}  Could not log in: {exc}")
        print("         Usually the server name or the account number.")
        print("         Check them against the TradeLocker login screen.")
        print()
        return 1
    except Exception as exc:                                   # noqa: BLE001
        print(f"{BAD}  Could not reach the broker: {exc}")
        print("         Check the internet connection and try again.")
        print()
        return 1

    print(f"{OK}  Logged in")
    print(f"{OK}  Using account {broker.account_id}")
    if not chosen_account:
        print("         (picked automatically. If that is the wrong one, put")
        print("          the right number in TRADELOCKER_ACCOUNT in .env)")

    try:
        account = broker.get_account()
        print(f"{OK}  Balance ${account.balance:,.2f} {account.currency}"
              f"   (equity ${account.equity:,.2f})")
    except Exception as exc:                                   # noqa: BLE001
        print(f"{BAD}  Logged in, but could not read the account: {exc}")
        print("         The account number is probably from a different tab.")
        print()
        return 1

    # Symbol naming is where firms differ most -- XAUUSD, XAUUSD.x, GOLD.
    found = None
    for symbol in ("XAUUSD", "XAUUSD.x", "XAU/USD", "GOLD"):
        try:
            bid, ask = broker.get_price(symbol)
            spread = (ask - bid) / ((ask + bid) / 2) * 100
            print(f"{OK}  Gold is {symbol}: bid {bid:,.2f} / ask {ask:,.2f}"
                  f"   (spread {spread:.4f}%)")
            found = symbol
            break
        except Exception:                                      # noqa: BLE001
            continue

    if not found:
        print(f"{BAD}  Logged in fine, but could not find gold prices.")
        print("         Look in TradeLocker for what gold is called there,")
        print("         then pass it with --symbols THATNAME")
    print()

    try:
        positions = broker.get_positions()
        print(f"{OK}  {len(positions)} position(s) currently open")
    except Exception:                                          # noqa: BLE001
        pass

    print()
    if found:
        print("Everything works. Next, from CONNECT.md step 3:")
        print(f"  python3 run.py --broker tradelocker --mode demo \\")
        print(f"    --strategies gold_scalper --symbols {found} --verbose")
    else:
        print("Login works but the gold symbol needs sorting first.")
    print()
    return 0 if found else 1


if __name__ == "__main__":
    sys.exit(main())
