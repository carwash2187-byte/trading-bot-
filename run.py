#!/usr/bin/env python3
"""Entry point for one scheduled trading cycle.

Run this from cron, a systemd timer, or a GitHub Actions workflow. It performs
exactly one pass and exits — no long-lived process to wedge or leak.

    */5 * * * * cd /path/to/tradebot && ./run.py --symbols XAUUSD >> logs/bot.log 2>&1

Everything defaults to paper trading. Going live needs both ``--mode live`` on
the command line and ``TRADEBOT_ALLOW_LIVE=yes`` in the environment.
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import timedelta
from pathlib import Path

from tradebot.brokers.base import TradingMode
from tradebot.brokers.paper import PaperBroker
from tradebot.news.calendar import EconomicCalendar, NewsDetector
from tradebot.risk.journal import TradeJournal
from tradebot.risk.limits import RiskLimits, RiskManager, RiskState
from tradebot.runtime.cycle import TradingCycle
from tradebot.runtime.lock import AlreadyRunning, InstanceLock
from tradebot.runtime.state import StateStore
from tradebot.runtime.watchdog import Heartbeat
from tradebot.strategy.base import NoOpStrategy

log = logging.getLogger("tradebot")


def build_broker(args):
    """Construct the requested adapter. Paper is the default everywhere."""
    mode = TradingMode(args.mode)

    if args.broker == "paper":
        broker = PaperBroker(starting_balance=args.balance, mode=TradingMode.PAPER)
        broker.connect()
        # A simulator needs a price before it can quote anything.
        for symbol in args.symbols:
            broker.set_price(symbol, args.seed_price)
        return broker

    if args.broker == "tradelocker":
        from tradebot.brokers.tradelocker import TradeLockerBroker

        return TradeLockerBroker(
            username=args.username, password=args.password, server=args.server,
            account_id=args.account, mode=mode,
        )

    if args.broker == "mt5":
        from tradebot.brokers.mt5 import MT5Broker

        return MT5Broker(
            login=int(args.account or 0), password=args.password,
            server=args.server, mode=mode,
        )

    raise SystemExit(f"unknown broker {args.broker!r}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run one trading cycle.")
    parser.add_argument("--broker", default="paper",
                        choices=["paper", "tradelocker", "mt5"])
    parser.add_argument("--mode", default="paper",
                        choices=["paper", "demo", "live"],
                        help="live also requires TRADEBOT_ALLOW_LIVE=yes")
    parser.add_argument("--symbols", nargs="+", default=["XAUUSD"])
    parser.add_argument("--account", default="")
    parser.add_argument("--username", default="")
    parser.add_argument("--password", default="")
    parser.add_argument("--server", default="")
    parser.add_argument("--balance", type=float, default=10_000.0)
    parser.add_argument("--seed-price", type=float, default=2000.0,
                        help="paper broker only: starting price")
    parser.add_argument("--risk-per-trade", type=float, default=0.01)
    parser.add_argument("--daily-loss-limit", type=float, default=0.03)
    parser.add_argument("--max-drawdown-limit", type=float, default=0.06)
    parser.add_argument("--news-url", default="",
                        help="economic calendar JSON endpoint")
    parser.add_argument("--data-dir", default="run")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )

    data_dir = Path(args.data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)

    # Refuse to start if another copy is mid-cycle. Skipping this run is
    # always safer than double-trading the same account.
    try:
        lock = InstanceLock(data_dir / "bot.lock").acquire()
    except AlreadyRunning as err:
        log.warning("%s", err)
        return 0

    try:
        state_store = StateStore(data_dir / "risk_state.json")
        loaded = state_store.load()
        if loaded.recovered:
            log.warning("risk state was corrupt; recovered to defaults "
                        "(bad file kept at %s)", loaded.backup_path)
        risk_state = RiskState.from_dict(loaded.data)

        limits = RiskLimits(
            risk_per_trade=args.risk_per_trade,
            daily_loss_limit=args.daily_loss_limit,
            max_drawdown_limit=args.max_drawdown_limit,
        )
        risk = RiskManager(limits, risk_state)

        news = None
        if args.news_url:
            calendar = EconomicCalendar(data_dir / "calendar.json")
            try:
                count = calendar.refresh_from_url(args.news_url)
                log.info("calendar loaded: %d events", count)
            except Exception as err:  # noqa: BLE001 - never block trading on news
                log.warning("calendar unavailable (%s); continuing without it", err)
            news = NewsDetector(calendar)

        broker = build_broker(args)
        journal = TradeJournal(data_dir / "journal.jsonl", starting_balance=args.balance)

        cycle = TradingCycle(
            broker=broker,
            strategy=NoOpStrategy(),     # <- plug your strategy in here
            risk=risk,
            journal=journal,
            symbols=[s.upper() for s in args.symbols],
            news=news,
        )

        report = cycle.run_once()
        state_store.save(risk.state.to_dict())
        Heartbeat(data_dir / "heartbeat.json").beat(ok=report.ok, note=report.summary())

        if report.halted:
            log.warning("RISK HALT active: %s", report.halt_reason)
        for err in report.errors:
            log.error("cycle error: %s", err)

        return 0 if report.ok else 1
    finally:
        lock.release()


if __name__ == "__main__":
    sys.exit(main())
