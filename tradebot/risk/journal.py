"""Persistent trade journal with broker reconciliation.

Every fill is appended to a JSONL file — append-only, one JSON object per
line, so a crash mid-write costs at most the last record instead of the whole
file.

The reconciliation check exists because a local P&L total that has silently
drifted from the broker's balance is the symptom of a contract-multiplier bug,
a missed fill, or a double-counted trade. Comparing the two on a schedule turns
a silent wrong number into a loud one.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from ..brokers.base import Fill, OrderSide


@dataclass
class JournalEntry:
    """One completed round trip, or one leg of one."""

    ticket: str
    symbol: str
    side: str
    lots: float
    entry_price: float
    exit_price: float | None
    opened_at: str
    closed_at: str | None
    realized_pnl: float
    commission: float = 0.0
    reason: str = ""
    note: str = ""

    def to_json(self) -> str:
        return json.dumps(asdict(self), separators=(",", ":"))

    @classmethod
    def from_dict(cls, raw: dict) -> "JournalEntry":
        return cls(
            ticket=str(raw["ticket"]),
            symbol=str(raw["symbol"]),
            side=str(raw["side"]),
            lots=float(raw["lots"]),
            entry_price=float(raw["entry_price"]),
            exit_price=None if raw.get("exit_price") is None else float(raw["exit_price"]),
            opened_at=str(raw["opened_at"]),
            closed_at=raw.get("closed_at"),
            realized_pnl=float(raw.get("realized_pnl", 0.0)),
            commission=float(raw.get("commission", 0.0)),
            reason=str(raw.get("reason", "")),
            note=str(raw.get("note", "")),
        )


@dataclass
class Reconciliation:
    """Result of comparing journal totals against the broker's balance."""

    journal_balance: float
    broker_balance: float
    difference: float
    tolerance: float
    matches: bool

    def describe(self) -> str:
        verdict = "OK" if self.matches else "MISMATCH"
        return (
            f"[{verdict}] journal={self.journal_balance:.2f} "
            f"broker={self.broker_balance:.2f} diff={self.difference:+.2f} "
            f"(tolerance {self.tolerance:.2f})"
        )


class TradeJournal:
    """Append-only JSONL journal of realised trades."""

    def __init__(self, path: str | Path, starting_balance: float = 0.0) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.starting_balance = starting_balance

    # -- writing ---------------------------------------------------------

    def record(self, entry: JournalEntry) -> None:
        """Append one entry, flushing immediately so a crash cannot lose it."""
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(entry.to_json() + "\n")
            fh.flush()

    def record_close(
        self,
        ticket: str,
        symbol: str,
        side: OrderSide,
        lots: float,
        entry_price: float,
        exit_price: float,
        realized_pnl: float,
        opened_at: datetime,
        closed_at: datetime | None = None,
        commission: float = 0.0,
        reason: str = "",
    ) -> JournalEntry:
        entry = JournalEntry(
            ticket=ticket,
            symbol=symbol,
            side=side.value if isinstance(side, OrderSide) else str(side),
            lots=lots,
            entry_price=entry_price,
            exit_price=exit_price,
            opened_at=opened_at.isoformat(),
            closed_at=(closed_at or datetime.now(timezone.utc)).isoformat(),
            realized_pnl=realized_pnl,
            commission=commission,
            reason=reason,
        )
        self.record(entry)
        return entry

    # -- reading ---------------------------------------------------------

    def entries(self) -> list[JournalEntry]:
        """Load all entries, skipping any line torn by a crash."""
        if not self.path.exists():
            return []
        out: list[JournalEntry] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                out.append(JournalEntry.from_dict(json.loads(line)))
            except (json.JSONDecodeError, KeyError, ValueError):
                # A partial final line is expected after an unclean shutdown.
                continue
        return out

    # -- analysis --------------------------------------------------------

    def realized_pnl(self) -> float:
        return sum(e.realized_pnl for e in self.entries())

    def total_commission(self) -> float:
        return sum(e.commission for e in self.entries())

    def expected_balance(self) -> float:
        return self.starting_balance + self.realized_pnl()

    def stats(self) -> dict:
        rows = [e for e in self.entries() if e.closed_at]
        wins = [e for e in rows if e.realized_pnl > 0]
        losses = [e for e in rows if e.realized_pnl < 0]
        gross_win = sum(e.realized_pnl for e in wins)
        gross_loss = abs(sum(e.realized_pnl for e in losses))
        return {
            "trades": len(rows),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": (len(wins) / len(rows)) if rows else 0.0,
            "net_pnl": sum(e.realized_pnl for e in rows),
            "gross_profit": gross_win,
            "gross_loss": gross_loss,
            "profit_factor": (gross_win / gross_loss) if gross_loss else float("inf"),
            "avg_win": (gross_win / len(wins)) if wins else 0.0,
            "avg_loss": (-gross_loss / len(losses)) if losses else 0.0,
        }

    # -- the important one -----------------------------------------------

    def reconcile(self, broker_balance: float, tolerance: float = 0.01) -> Reconciliation:
        """Compare the journal's implied balance against the broker's.

        A persistent mismatch means the local money maths is wrong. Treat it as
        a stop-trading condition, not a rounding curiosity.
        """
        expected = self.expected_balance()
        diff = expected - broker_balance
        return Reconciliation(
            journal_balance=expected,
            broker_balance=broker_balance,
            difference=diff,
            tolerance=tolerance,
            matches=abs(diff) <= tolerance,
        )
