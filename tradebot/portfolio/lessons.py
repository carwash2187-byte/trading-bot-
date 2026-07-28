"""Carry what was learned from one funded account into the next.

A prop account dies and is replaced. Without something like this, every
replacement starts as ignorant as the first one and the same size mistake gets
paid for over and over.

The thing worth learning between accounts is **position size**. Strategy
selection is already handled by the portfolio manager, and entry rules should
not be rewritten from a handful of trades. Size is different: each dead account
is one clean, complete observation of "at this size, the account survived N
days and paid out $X", and those observations stack up honestly.

What this deliberately does NOT do is adjust anything mid-account. A rule
invented from two bad Tuesdays is noise, and a bot that rewrites itself after
every loss destroys itself. This only reconsiders when an account ends, and
only after several accounts have reported in.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from ..runtime.state import StateStore

log = logging.getLogger("tradebot.lessons")

BREACHED = "breached"      # hit the daily or total loss limit
RETIRED = "retired"        # closed while still alive


@dataclass
class AccountRecord:
    """One funded account, from purchase to death."""

    size: float                 # the leverage multiple it traded at
    days_lived: int
    withdrawn: float
    payouts: int
    ended: str                  # BREACHED or RETIRED
    fee: float = 100.0
    started_at: str = ""
    ended_at: str = ""

    @property
    def net(self) -> float:
        """Profit after the cost of buying the account."""
        return self.withdrawn - self.fee

    @property
    def per_day(self) -> float:
        return (self.net / self.days_lived) if self.days_lived else 0.0


@dataclass
class SizeVerdict:
    """What the accumulated accounts say about one position size."""

    size: float
    accounts: int
    avg_net: float
    avg_days: float
    breach_rate: float
    per_day: float

    def describe(self) -> str:
        return (
            f"{self.size:.1f}x  accounts={self.accounts:<3} "
            f"net=${self.avg_net:+8.0f}  days={self.avg_days:5.1f}  "
            f"breached={self.breach_rate * 100:4.0f}%  ${self.per_day:+.2f}/day"
        )


class LessonBook:
    """Remembers every account that has been run and sizes the next one.

    Args:
        path: where the record is kept. Survives account resets on purpose --
            that persistence is the entire point.
        min_accounts: how many accounts a size must have before its result is
            trusted. One dead account proves nothing; a size can breach early
            purely on a bad run, and reacting to that is how a bot talks itself
            down to trading nothing.
        default_size: what to use before enough evidence exists.
        step: how far the size may move in one decision. Capped so a single
            unlucky account cannot swing the next one wildly.
    """

    def __init__(
        self,
        path: str | Path = "run/lessons.json",
        min_accounts: int = 3,
        default_size: float = 3.0,
        step: float = 0.5,
        floor: float = 1.0,
        ceiling: float = 5.0,
    ) -> None:
        self.store = StateStore(path, defaults={"accounts": []})
        self.min_accounts = min_accounts
        self.default_size = default_size
        self.step = step
        self.floor = floor
        self.ceiling = ceiling
        self.records: list[AccountRecord] = []
        self._load()

    # -- persistence -----------------------------------------------------

    def _load(self) -> None:
        raw = self.store.load().data.get("accounts", [])
        for row in raw:
            if not isinstance(row, dict):
                continue
            try:
                self.records.append(
                    AccountRecord(
                        size=float(row["size"]),
                        days_lived=int(row["days_lived"]),
                        withdrawn=float(row["withdrawn"]),
                        payouts=int(row.get("payouts", 0)),
                        ended=str(row.get("ended", BREACHED)),
                        fee=float(row.get("fee", 100.0)),
                        started_at=str(row.get("started_at", "")),
                        ended_at=str(row.get("ended_at", "")),
                    )
                )
            except (KeyError, TypeError, ValueError):
                # A malformed row is dropped rather than taking the whole
                # history down with it.
                continue

    def _save(self) -> None:
        self.store.save(
            {
                "accounts": [
                    {
                        "size": r.size,
                        "days_lived": r.days_lived,
                        "withdrawn": r.withdrawn,
                        "payouts": r.payouts,
                        "ended": r.ended,
                        "fee": r.fee,
                        "started_at": r.started_at,
                        "ended_at": r.ended_at,
                    }
                    for r in self.records
                ]
            }
        )

    # -- recording -------------------------------------------------------

    def record_account(
        self,
        size: float,
        days_lived: int,
        withdrawn: float,
        payouts: int,
        ended: str = BREACHED,
        fee: float = 100.0,
        now: datetime | None = None,
    ) -> AccountRecord:
        """Log a finished account. Call this the moment one dies or is closed."""
        now = now or datetime.now(timezone.utc)
        record = AccountRecord(
            size=size,
            days_lived=days_lived,
            withdrawn=withdrawn,
            payouts=payouts,
            ended=ended,
            fee=fee,
            ended_at=now.isoformat(),
        )
        self.records.append(record)
        self._save()
        log.info(
            "account closed: %.1fx lived %dd, withdrew $%.0f over %d payouts (%s)",
            size, days_lived, withdrawn, payouts, ended,
        )
        return record

    # -- analysis --------------------------------------------------------

    def verdicts(self) -> dict[float, SizeVerdict]:
        """Score every size that has been tried."""
        buckets: dict[float, list[AccountRecord]] = {}
        for r in self.records:
            buckets.setdefault(round(r.size, 1), []).append(r)

        out: dict[float, SizeVerdict] = {}
        for size, rows in buckets.items():
            breaches = sum(1 for r in rows if r.ended == BREACHED)
            days = sum(r.days_lived for r in rows)
            net = sum(r.net for r in rows)
            out[size] = SizeVerdict(
                size=size,
                accounts=len(rows),
                avg_net=net / len(rows),
                avg_days=days / len(rows),
                breach_rate=breaches / len(rows),
                # Money per day is the honest yardstick: a size that earns more
                # but dies sooner is not automatically better, and this is the
                # only measure that prices both at once.
                per_day=(net / days) if days else 0.0,
            )
        return out

    def recommend_size(self) -> tuple[float, str]:
        """Pick the size for the next account, with the reason why."""
        verdicts = self.verdicts()
        proven = {s: v for s, v in verdicts.items() if v.accounts >= self.min_accounts}

        if not proven:
            tried = sum(v.accounts for v in verdicts.values())
            return self.default_size, (
                f"only {tried} account(s) on record; need {self.min_accounts} at a "
                f"size before trusting it, so holding at {self.default_size:.1f}x"
            )

        best = max(proven.values(), key=lambda v: v.per_day)
        last = self.records[-1].size

        # Move toward the best size gradually. A jump straight to it would let
        # one lucky run at an untested size dominate everything that follows.
        if best.size > last:
            target = min(last + self.step, best.size)
        elif best.size < last:
            target = max(last - self.step, best.size)
        else:
            target = last
        target = max(self.floor, min(self.ceiling, round(target, 1)))

        return target, (
            f"{best.size:.1f}x earns the most per day (${best.per_day:+.2f} over "
            f"{best.accounts} accounts, {best.breach_rate * 100:.0f}% breached); "
            f"moving {last:.1f}x -> {target:.1f}x"
        )

    def report(self) -> str:
        if not self.records:
            return "no accounts recorded yet"
        lines = [f"{len(self.records)} account(s) on record:"]
        for size in sorted(self.verdicts()):
            lines.append("  " + self.verdicts()[size].describe())
        size, why = self.recommend_size()
        lines.append(f"\nnext account: {size:.1f}x  ({why})")
        return "\n".join(lines)
