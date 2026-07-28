"""The portfolio manager: run a stack of strategies, bench the ones going cold.

The premise is that no edge lasts. Walk-forward testing on this project showed
the same strategy winning 2.09x its losses in 2024, 1.62x in 2025 and *losing*
money in 2026 -- same code, same settings, decayed market. A second, unrelated
market decayed on the same timetable. Searching harder for a strategy that
never rots is searching for something that does not exist.

So this does not try. It assumes every strategy dies, runs several at once, and
takes each one out of service when its recent record says it has stopped
working. A benched strategy keeps being scored on paper, so one that recovers
can earn its way back rather than being deleted on a bad fortnight.

That means the manager's job is survival, not selection. It cannot make a bad
strategy good; it can stop a dead one bleeding while the others carry on.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ..runtime.state import StateStore
from ..risk.journal import TradeJournal
from ..strategy.base import Strategy
from .scorecard import COLD, HEALTHY, Score, score_strategies

log = logging.getLogger("tradebot.portfolio")

ACTIVE = "active"
BENCHED = "benched"


@dataclass
class Slot:
    """One strategy's standing in the portfolio."""

    name: str
    status: str = ACTIVE
    since: str = ""
    reason: str = ""

    @property
    def is_active(self) -> bool:
        return self.status == ACTIVE


@dataclass
class ReviewReport:
    """What the manager changed, and why."""

    reviewed_at: datetime
    scores: dict[str, Score] = field(default_factory=dict)
    benched: list[str] = field(default_factory=list)
    restored: list[str] = field(default_factory=list)
    active: list[str] = field(default_factory=list)

    def summary(self) -> str:
        parts = [f"portfolio: {len(self.active)} active"]
        if self.benched:
            parts.append("benched " + ", ".join(self.benched))
        if self.restored:
            parts.append("restored " + ", ".join(self.restored))
        return "; ".join(parts)

    def table(self) -> str:
        if not self.scores:
            return "no closed trades in the scoring window yet"
        lines = []
        for name in sorted(self.scores):
            standing = "ACTIVE" if name in self.active else "benched"
            lines.append(f"  {standing:<8} {self.scores[name].describe()}")
        return "\n".join(lines)


class PortfolioManager:
    """Keeps a roster of strategies and decides which may trade.

    Args:
        roster: every strategy that could run, healthy or not.
        journal: where results are read from.
        state_path: where standings persist between scheduled runs.
        window_days: how far back a report card looks.
        min_trades: below this, a strategy is judged unproven and left alone.
        min_profit_factor: winnings-to-losses ratio required to stay active.
        probation_days: how long a benched strategy must wait before it can
            return, so it is not flipped in and out on noise.
    """

    def __init__(
        self,
        roster: list[Strategy],
        journal: TradeJournal,
        state_path: str | Path = "run/portfolio.json",
        window_days: int = 14,
        min_trades: int = 10,
        min_profit_factor: float = 1.0,
        probation_days: int = 14,
    ) -> None:
        self.roster = {s.name: s for s in roster}
        self.journal = journal
        self.window_days = window_days
        self.min_trades = min_trades
        self.min_profit_factor = min_profit_factor
        self.probation_days = probation_days
        self.store = StateStore(state_path, defaults={"slots": {}})
        self.slots: dict[str, Slot] = {}
        self._load()

    # -- persistence -----------------------------------------------------

    def _load(self) -> None:
        raw = self.store.load().data.get("slots", {})
        for name in self.roster:
            saved = raw.get(name)
            if isinstance(saved, dict):
                self.slots[name] = Slot(
                    name=name,
                    status=str(saved.get("status", ACTIVE)),
                    since=str(saved.get("since", "")),
                    reason=str(saved.get("reason", "")),
                )
            else:
                # A strategy added to the roster since the last run starts
                # active; it has no record yet, so there is nothing to hold
                # against it.
                self.slots[name] = Slot(name=name, status=ACTIVE)

    def _save(self) -> None:
        self.store.save(
            {
                "slots": {
                    name: {
                        "status": slot.status,
                        "since": slot.since,
                        "reason": slot.reason,
                    }
                    for name, slot in self.slots.items()
                }
            }
        )

    # -- the decision ----------------------------------------------------

    def active_strategies(self) -> list[Strategy]:
        """The strategies currently cleared to place orders."""
        return [self.roster[n] for n, s in self.slots.items() if s.is_active]

    def review(self, now: datetime | None = None) -> ReviewReport:
        """Re-score everything and move strategies on or off the bench."""
        now = now or datetime.now(timezone.utc)
        scores = score_strategies(
            self.journal,
            window_days=self.window_days,
            min_trades=self.min_trades,
            min_profit_factor=self.min_profit_factor,
            now=now,
        )
        report = ReviewReport(reviewed_at=now, scores=scores)

        for name, slot in self.slots.items():
            score = scores.get(name)

            if slot.is_active:
                # Only a verdict backed by enough trades can bench a strategy.
                # An unproven one is left running precisely because we do not
                # yet know anything about it.
                if score is not None and score.verdict == COLD:
                    slot.status = BENCHED
                    slot.since = now.isoformat()
                    slot.reason = (
                        f"profit factor {score.profit_factor:.2f} below "
                        f"{self.min_profit_factor:.2f} over {score.trades} trades"
                    )
                    report.benched.append(name)
                    log.warning("benched %s: %s", name, slot.reason)
                continue

            if self._may_return(slot, score, now):
                slot.status = ACTIVE
                slot.since = now.isoformat()
                slot.reason = "recovered"
                report.restored.append(name)
                log.info("restored %s to the active stack", name)

        report.active = [n for n, s in self.slots.items() if s.is_active]
        self._save()
        log.info(report.summary())
        return report

    def _may_return(self, slot: Slot, score: Score | None, now: datetime) -> bool:
        """A benched strategy returns only after serving time *and* proving it."""
        if score is None or score.verdict != HEALTHY:
            return False
        if not slot.since:
            return True
        try:
            benched_at = datetime.fromisoformat(slot.since)
        except ValueError:
            return True
        if benched_at.tzinfo is None:
            benched_at = benched_at.replace(tzinfo=timezone.utc)
        return now - benched_at >= timedelta(days=self.probation_days)
