"""Circuit breakers and exposure caps.

Three independent guards, all broker-agnostic:

* **Daily loss** — once the account is down more than X% on the day, no new
  entries until the next trading day.
* **Max drawdown from peak** — once equity falls X% below its high-water mark,
  no new entries at all until an operator resets it.
* **Correlation cap** — at most N open positions per correlation group, so the
  bot cannot end up holding five different JPY pairs and calling it five trades
  when it is really one bet.

Breakers block *new entries*. They never force-close an open position on their
own: exits belong to the strategy and to the server-side brackets. Use
``Broker.close_all()`` explicitly if flattening on a breach is wanted.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone

from ..brokers.base import Position


class BreachReason(str):
    """Marker type so reasons read clearly in logs and journals."""


DAILY_LOSS = "daily_loss_limit"
MAX_DRAWDOWN = "max_drawdown_limit"
CORRELATION = "correlation_cap"
NO_BREACH = ""


@dataclass
class RiskDecision:
    """Whether a proposed entry is allowed, and why not if it isn't."""

    allowed: bool
    reason: str = NO_BREACH
    detail: str = ""

    def __bool__(self) -> bool:
        return self.allowed


@dataclass
class RiskLimits:
    """Configuration for the risk layer. All fractions, not percents."""

    risk_per_trade: float = 0.01        # 1% of equity per trade
    daily_loss_limit: float = 0.03      # halt for the day at -3%
    max_drawdown_limit: float = 0.06    # halt entirely at -6% from peak
    max_correlated_positions: int = 2
    max_total_positions: int = 5

    def __post_init__(self) -> None:
        for name in ("risk_per_trade", "daily_loss_limit", "max_drawdown_limit"):
            value = getattr(self, name)
            if not 0 < value < 1:
                raise ValueError(f"{name} must be a fraction between 0 and 1")
        if self.daily_loss_limit > self.max_drawdown_limit:
            raise ValueError(
                "daily_loss_limit above max_drawdown_limit: the daily breaker "
                "could never trip before the account-level one"
            )


@dataclass
class RiskState:
    """Mutable risk bookkeeping. Persisted between runs by the state store."""

    peak_equity: float = 0.0
    day_start_equity: float = 0.0
    current_day: str = ""
    halted: bool = False
    halt_reason: str = NO_BREACH

    def to_dict(self) -> dict:
        return {
            "peak_equity": self.peak_equity,
            "day_start_equity": self.day_start_equity,
            "current_day": self.current_day,
            "halted": self.halted,
            "halt_reason": self.halt_reason,
        }

    @classmethod
    def from_dict(cls, raw: dict) -> "RiskState":
        return cls(
            peak_equity=float(raw.get("peak_equity", 0.0)),
            day_start_equity=float(raw.get("day_start_equity", 0.0)),
            current_day=str(raw.get("current_day", "")),
            halted=bool(raw.get("halted", False)),
            halt_reason=str(raw.get("halt_reason", NO_BREACH)),
        )


class RiskManager:
    """Applies :class:`RiskLimits` against live equity and open positions."""

    def __init__(self, limits: RiskLimits, state: RiskState | None = None) -> None:
        self.limits = limits
        self.state = state or RiskState()

    # -- bookkeeping -----------------------------------------------------

    def update_equity(self, equity: float, now: datetime | None = None) -> None:
        """Record current equity, rolling the day over when the date changes.

        Must be called once per cycle, before :meth:`check_entry`.
        """
        now = now or datetime.now(timezone.utc)
        today = now.date().isoformat()

        if self.state.current_day != today:
            # New trading day: reset the daily baseline and clear a daily halt.
            self.state.current_day = today
            self.state.day_start_equity = equity
            if self.state.halt_reason == DAILY_LOSS:
                self.state.halted = False
                self.state.halt_reason = NO_BREACH

        if self.state.day_start_equity <= 0:
            self.state.day_start_equity = equity
        self.state.peak_equity = max(self.state.peak_equity, equity)

    # -- derived numbers -------------------------------------------------

    def daily_pnl_pct(self, equity: float) -> float:
        """Today's return as a fraction. Negative means down."""
        if self.state.day_start_equity <= 0:
            return 0.0
        return (equity - self.state.day_start_equity) / self.state.day_start_equity

    def drawdown_pct(self, equity: float) -> float:
        """Distance below the equity high-water mark, as a positive fraction."""
        if self.state.peak_equity <= 0:
            return 0.0
        return max(0.0, (self.state.peak_equity - equity) / self.state.peak_equity)

    # -- the gate --------------------------------------------------------

    def check_entry(
        self,
        equity: float,
        symbol: str,
        correlation_group: str | None,
        open_positions: list[Position],
        groups: dict[str, str | None] | None = None,
    ) -> RiskDecision:
        """Decide whether one more entry is permitted right now.

        Args:
            equity: Current account equity.
            symbol: Symbol being considered.
            correlation_group: Group of that symbol, e.g. ``"JPY"``.
            open_positions: Everything currently open on the account.
            groups: Map of open symbol -> its correlation group.
        """
        if self.state.halted:
            return RiskDecision(False, self.state.halt_reason, "risk manager is halted")

        drawdown = self.drawdown_pct(equity)
        if drawdown >= self.limits.max_drawdown_limit:
            self._halt(MAX_DRAWDOWN)
            return RiskDecision(
                False,
                MAX_DRAWDOWN,
                f"drawdown {drawdown:.2%} at/over limit {self.limits.max_drawdown_limit:.2%}",
            )

        daily = self.daily_pnl_pct(equity)
        if daily <= -self.limits.daily_loss_limit:
            self._halt(DAILY_LOSS)
            return RiskDecision(
                False,
                DAILY_LOSS,
                f"today {daily:.2%} at/over limit -{self.limits.daily_loss_limit:.2%}",
            )

        if len(open_positions) >= self.limits.max_total_positions:
            return RiskDecision(
                False,
                CORRELATION,
                f"{len(open_positions)} positions open, cap is "
                f"{self.limits.max_total_positions}",
            )

        if correlation_group:
            groups = groups or {}
            same = sum(
                1
                for pos in open_positions
                if (groups.get(pos.symbol) or None) == correlation_group
            )
            if same >= self.limits.max_correlated_positions:
                return RiskDecision(
                    False,
                    CORRELATION,
                    f"{same} positions already open in group {correlation_group!r}, "
                    f"cap is {self.limits.max_correlated_positions}",
                )

        return RiskDecision(True)

    # -- operator controls -----------------------------------------------

    def _halt(self, reason: str) -> None:
        self.state.halted = True
        self.state.halt_reason = reason

    def reset_halt(self) -> None:
        """Clear a halt. Deliberately manual for the drawdown breaker."""
        self.state.halted = False
        self.state.halt_reason = NO_BREACH

    def reset_peak(self, equity: float) -> None:
        """Re-baseline the high-water mark, e.g. after a deposit."""
        self.state.peak_equity = equity
