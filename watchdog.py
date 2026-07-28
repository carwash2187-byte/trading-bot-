#!/usr/bin/env python3
"""Watchdog entry point — checks the main job is still firing.

Run this on a slower schedule than the bot, and from a *different* mechanism.
A watchdog launched by the same cron that stopped working is not a watchdog.

    */20 * * * * cd /path/to/tradebot && ./watchdog.py --max-age 15

Exit codes: 0 healthy, 1 stale (so a monitoring tool can alert on it).
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import timedelta
from pathlib import Path

from tradebot.runtime.watchdog import Heartbeat, Watchdog

log = logging.getLogger("tradebot.watchdog")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check the bot is still running.")
    parser.add_argument("--data-dir", default="run")
    parser.add_argument("--max-age", type=float, default=15.0,
                        help="minutes before the heartbeat counts as stale")
    parser.add_argument("--restart", nargs=argparse.REMAINDER,
                        help="command to run when stale, e.g. --restart ./run.py")
    parser.add_argument("--max-restarts-per-hour", type=int, default=4)
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )

    data_dir = Path(args.data_dir)
    heartbeat = Heartbeat(data_dir / "heartbeat.json")
    dog = Watchdog(
        heartbeat=heartbeat,
        max_age=timedelta(minutes=args.max_age),
        restart_command=args.restart or None,
        max_restarts_per_hour=args.max_restarts_per_hour,
        state_path=data_dir / "watchdog.json",
    )

    status = dog.check()
    if status.stale:
        log.error("UNHEALTHY: %s", status.describe())
        return 1

    log.info("healthy: %s", status.describe())
    return 0


if __name__ == "__main__":
    sys.exit(main())
