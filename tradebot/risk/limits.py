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
    # Deliberately loose. MambaFX ends his own day on two losses -- "If the second
    # one doesn't work out, we are done for the day and we come back tomorrow" --
    # and that rule lives in the strategies as max_losses_per_day. At his stated
    # 10-25% risk, two losses is 20-50%, so a tighter percentage brake here would
    # trip before his rule could and would quietly replace it with mine.
    #
    # These were 3% and 6%, inherited from a prop firm's rulebook. This is Leo's
    # own account with nothing to breach, so they exist now only as a last-resort
    # backstop against something going genuinely wrong.
    # OFF by default. MambaFX ends his own day on two losses -- "If the second one
    # doesn't work out, we are done for the day and we come back tomorrow and we do
    # it again" -- and that rule lives in the strategies as max_losses_per_day.
    #
    # These were 3% and 6%, inherited from a prop firm's rulebook that has nothing
    # to do with Leo's own account. At his stated 10-25% risk a 3% daily limit trips
    # on the FIRST loss, so my brake fired before his rule could speak and quietly
    # replaced his method with mine. Set to a number to re-enable; None means his
    # rule is the only thing that stops the day.
    daily_loss_limit: float | None = None
    max_drawdown_limit: float | None = None
    max_correlated_positions: int = 2
    max_total_positions: int = 5
    # Halt at this fraction of each limit rather than at the limit itself.
    # 0.9 turns a 6% account-ending drawdown into a 5.4% stop, which leaves
    # room to be wrong about slippage, a gapping fill, or a stale equity read
    # -- all of which land on the wrong side of a threshold that cannot be
    # recovered from once crossed.
    safety_margin: float = 0.9
    # The account's leverage, for the margin-aware position cap. AquaFunded
    # gives 1:50. Used to stop a collapsed stop-distance ballooning the lot
    # count past what the account can even margin -- the broker would reject
    # that order anyway, but a bot that caps itself trades the capped size
    # instead of raising an alarm about a size it should never have asked for.
    leverage: float = 50.0
    # The account's opening balance, when known. This powers a guard that
    # needs NO stored state at all: the prop firm ends the account 6% below
    # this number, so with the number itself in hand the fatal line is a
    # constant. The stateful breakers above track peaks and daily baselines in
    # a file -- and an environment like GitHub Actions destroys that file
    # between runs, silently reducing them to no-ops. This one survives
    # anything, because there is nothing to lose.
    floor_balance: float = 0.0

    def __post_init__(self) -> None:
        if not 0 < self.risk_per_trade < 1:
            raise ValueError("risk_per_trade must be a fraction between 0 and 1")
        for name in ("daily_loss_limit", "max_drawdown_limit"):
            value = getattr(self, name)
            if value is None:
                continue        # off: the strategy's own rule ends the day
            if not 0 < value < 1:
                raise ValueError(f"{name} must be a fraction between 0 and 1")
        if (self.daily_loss_limit is not None
                and self.max_drawdown_limit is not None
                and self.daily_loss_limit > self.max_drawdown_limit):
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
    # Trades opened today, per strategy name. A strategy cannot count these for
    # itself: the only per-trade information in a StrategyContext is the list of
    # OPEN positions, so the moment a trade closes it stops being counted and a
    # "max 3 trades a day" rule silently becomes "max 3 at once". Measured on
    # MambaNY that let 4.4 trades a day through a cap set to 3.
    trades_today: dict = field(default_factory=dict)
    # Losing trades closed today, per strategy. "If the second one doesn't work
    # out, we are done for the day and we come back tomorrow and we do it again."
    losses_today: dict = field(default_factory=dict)
    # "First trade works out, we're done. We don't go for a second." A WIN ends
    # his day just as two losses do, which nothing in this project counted until
    # now -- the bot would happily take a second trade after a winner all day.
    wins_today: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "peak_equity": self.peak_equity,
            "day_start_equity": self.day_start_equity,
            "current_day": self.current_day,
            "halted": self.halted,
            "halt_reason": self.halt_reason,
            "trades_today": dict(self.trades_today),
            "losses_today": dict(self.losses_today),
            "wins_today": dict(self.wins_today),
        }

    @classmethod
    def from_dict(cls, raw: dict) -> "RiskState":
        return cls(
            peak_equity=float(raw.get("peak_equity", 0.0)),
            day_start_equity=float(raw.get("day_start_equity", 0.0)),
            current_day=str(raw.get("current_day", "")),
            halted=bool(raw.get("halted", False)),
            halt_reason=str(raw.get("halt_reason", NO_BREACH)),
            trades_today={
                str(k): int(v)
                for k, v in dict(raw.get("trades_today", {})).items()
            },
            wins_today={
                str(k): int(v)
                for k, v in dict(raw.get("wins_today", {})).items()
            },
            losses_today={
                str(k): int(v)
                for k, v in dict(raw.get("losses_today", {})).items()
            },
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
            self.state.trades_today = {}
            self.state.losses_today = {}
            self.state.wins_today = {}
            if self.state.halt_reason == DAILY_LOSS:
                self.state.halted = False
                self.state.halt_reason = NO_BREACH

        if self.state.day_start_equity <= 0:
            self.state.day_start_equity = equity
        self.state.peak_equity = max(self.state.peak_equity, equity)

    def record_entry(self, strategy: str) -> None:
        """Count a trade opened today by ``strategy``."""
        if not strategy:
            return
        self.state.trades_today[strategy] = self.trades_today(strategy) + 1

    def trades_today(self, strategy: str) -> int:
        """How many trades ``strategy`` has opened today."""
        return int(self.state.trades_today.get(strategy, 0))

    def record_loss(self, strategy: str) -> None:
        """Count a losing trade closed today by ``strategy``."""
        if not strategy:
            return
        self.state.losses_today[strategy] = self.losses_today(strategy) + 1

    def record_win(self, strategy: str) -> None:
        """"First trade works out, we're done. We don't go for a second"."""
        self.state.wins_today[strategy] = self.wins_today(strategy) + 1

    def wins_today(self, strategy: str) -> int:
        """How many winners this strategy has banked today."""
        return int(self.state.wins_today.get(strategy, 0))

    def losses_today(self, strategy: str) -> int:
        """How many losing trades ``strategy`` has closed today."""
        return int(self.state.losses_today.get(strategy, 0))

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

        # The stateless floor, checked first because it is the one guard that
        # cannot have lost its memory. The others compare against a peak and a
        # daily baseline read from a state file; on a host that wipes the
        # filesystem between runs (GitHub Actions does) that file is gone and
        # they silently compare against freshly-seeded values. This check is a
        # constant against a constant.
        #
        # It halts one full trade-loss ABOVE the line, not at it. Walk-forward
        # showed why: a stretch dipped to $2,448 against a $2,477 death line,
        # and a floor that only blocks new entries still lets the trade that is
        # already open ride through the line. The rule that actually protects
        # the account is: never be in a position whose full loss would cross it.
        if self.limits.floor_balance > 0 and self.limits.max_drawdown_limit is not None:
            floor = self.limits.floor_balance * (
                1
                - self.limits.max_drawdown_limit * self.limits.safety_margin
                + self.limits.risk_per_trade
            )
            if equity <= floor:
                self._halt(MAX_DRAWDOWN)
                return RiskDecision(
                    False,
                    MAX_DRAWDOWN,
                    f"equity {equity:,.2f} at/under the entry floor {floor:,.2f} "
                    f"(account opened at {self.limits.floor_balance:,.2f}; the "
                    f"firm ends it {self.limits.max_drawdown_limit:.0%} below "
                    f"that, and one more full loss must not be able to reach it)",
                )

        # Stop short of the limit rather than on it. Two reasons, and the
        # second is the one that bites:
        #
        # Binary floating point cannot represent 6% exactly. A drawdown of
        # precisely the limit computes as 0.059999999999999984, which is NOT
        # >= 0.06, so the check passes and trading continues at the exact
        # moment the account is being closed.
        #
        # And a prop firm ends the account the instant the line is touched,
        # with no appeal. Riding right up to a threshold whose breach is fatal
        # and unrecoverable is worth giving up a fraction of a percent to
        # avoid -- the last 0.6% of a 6% allowance is not worth the account.
        # The same one-full-loss headroom applies to the stateful breakers: an
        # entry is refused if this trade losing outright would carry the
        # account past the stop. Without it the breakers only react AFTER the
        # damage, and against a fatal, unappealable limit "after" is too late.
        if self.limits.max_drawdown_limit is not None:
            drawdown = self.drawdown_pct(equity) + self.limits.risk_per_trade
            drawdown_stop = self.limits.max_drawdown_limit * self.limits.safety_margin
        else:
            drawdown = drawdown_stop = None
        if drawdown is not None and drawdown >= drawdown_stop:
            self._halt(MAX_DRAWDOWN)
            return RiskDecision(
                False,
                MAX_DRAWDOWN,
                f"drawdown {drawdown:.2%} at/over the stop at {drawdown_stop:.2%} "
                f"(the account itself ends at {self.limits.max_drawdown_limit:.2%})",
            )

        if self.limits.daily_loss_limit is not None:
            daily = self.daily_pnl_pct(equity) - self.limits.risk_per_trade
            daily_stop = self.limits.daily_loss_limit * self.limits.safety_margin
        else:
            daily = daily_stop = None
        if daily is not None and daily <= -daily_stop:
            self._halt(DAILY_LOSS)
            return RiskDecision(
                False,
                DAILY_LOSS,
                f"today {daily:.2%} at/over the stop at -{daily_stop:.2%} "
                f"(the firm's limit is -{self.limits.daily_loss_limit:.2%})",
            )

        # One position per symbol, always. This is not a preference, it is the
        # last line of defence against a specific way of destroying an account:
        # a strategy is shown only the positions attributed to it, so if that
        # attribution fails for any reason -- a broker that does not return the
        # order comment, a renamed strategy, a restart -- it believes it is flat
        # while holding a position, and opens another every cycle. RSI can sit
        # oversold for hours, so that is a dozen entries stacked at several
        # times the intended size.
        #
        # Checked here rather than in the strategy because it must hold no
        # matter which strategy asks and no matter what it thinks it owns.
        held = [p for p in open_positions if p.symbol.upper() == symbol.upper()]
        if held:
            return RiskDecision(
                False,
                CORRELATION,
                f"already holding {symbol}; refusing to stack a second position",
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
