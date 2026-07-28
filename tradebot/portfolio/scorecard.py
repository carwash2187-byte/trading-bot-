"""Per-strategy report cards, read from the trade journal.

Scoring is deliberately per *strategy*, not per account. An account total says
"this month was bad"; it cannot say *which* of five running strategies caused
it. Without that split there is nothing to bench, which is the whole point of
the portfolio manager.

The window is rolling and short on purpose. A strategy's lifetime record is the
wrong question -- an edge that worked for two years and died last month still
has a flattering lifetime number, and that is exactly the strategy that must be
switched off.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from ..risk.journal import JournalEntry, TradeJournal

HEALTHY = "healthy"
COLD = "cold"
UNPROVEN = "unproven"


@dataclass
class Score:
    """One strategy's record over the scoring window."""

    strategy: str
    trades: int
    wins: int
    net_pnl: float
    gross_profit: float
    gross_loss: float
    verdict: str

    @property
    def win_rate(self) -> float:
        return (self.wins / self.trades) if self.trades else 0.0

    @property
    def profit_factor(self) -> float:
        """Gross winnings divided by gross losses.

        Infinity when there are no losses yet, which is a small sample rather
        than a perfect strategy -- ``verdict`` is what guards against acting
        on that.
        """
        if self.gross_loss > 0:
            return self.gross_profit / self.gross_loss
        return float("inf") if self.gross_profit > 0 else 0.0

    @property
    def expectancy(self) -> float:
        """Average money per trade. The number that actually pays out."""
        return (self.net_pnl / self.trades) if self.trades else 0.0

    def describe(self) -> str:
        pf = self.profit_factor
        pf_text = "inf" if pf == float("inf") else f"{pf:.2f}"
        return (
            f"{self.strategy:<16} {self.verdict:<9} "
            f"trades={self.trades:<4} win={self.win_rate * 100:5.1f}% "
            f"pf={pf_text:<6} net={self.net_pnl:+.2f}"
        )


def _parse(stamp: str | None) -> datetime | None:
    if not stamp:
        return None
    try:
        parsed = datetime.fromisoformat(stamp)
    except ValueError:
        return None
    # Journal entries written by older code may lack a timezone; assume UTC
    # rather than discarding the row, since a naive/aware comparison raises.
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def score_entries(
    entries: list[JournalEntry],
    min_trades: int,
    min_profit_factor: float,
) -> dict[str, Score]:
    """Build one report card per strategy from already-filtered entries."""
    buckets: dict[str, list[JournalEntry]] = {}
    for entry in entries:
        buckets.setdefault(entry.strategy or "untagged", []).append(entry)

    scores: dict[str, Score] = {}
    for name, rows in buckets.items():
        wins = [r for r in rows if r.realized_pnl > 0]
        losses = [r for r in rows if r.realized_pnl < 0]
        gross_profit = sum(r.realized_pnl for r in wins)
        gross_loss = abs(sum(r.realized_pnl for r in losses))

        score = Score(
            strategy=name,
            trades=len(rows),
            wins=len(wins),
            net_pnl=sum(r.realized_pnl for r in rows),
            gross_profit=gross_profit,
            gross_loss=gross_loss,
            verdict=UNPROVEN,
        )
        if score.trades < min_trades:
            # Too few trades to distinguish skill from luck. Not a pass mark --
            # judgement is withheld, and the caller decides what to do with it.
            score.verdict = UNPROVEN
        elif score.profit_factor >= min_profit_factor:
            score.verdict = HEALTHY
        else:
            score.verdict = COLD
        scores[name] = score
    return scores


def score_strategies(
    journal: TradeJournal,
    window_days: int = 14,
    min_trades: int = 10,
    min_profit_factor: float = 1.0,
    now: datetime | None = None,
) -> dict[str, Score]:
    """Score every strategy on trades closed within the rolling window."""
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=window_days)

    recent = []
    for entry in journal.entries():
        closed = _parse(entry.closed_at)
        if closed is None or closed < cutoff:
            continue
        recent.append(entry)

    return score_entries(recent, min_trades, min_profit_factor)
