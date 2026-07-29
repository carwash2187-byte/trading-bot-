"""The trading cycle: one guarded pass over one account.

Design intent is that this runs as a *scheduled job* — cron, systemd timer,
GitHub Actions — not as an always-on daemon. A process that exits after every
pass cannot leak memory, cannot drift into a wedged state, and is restarted for
free by the scheduler. The watchdog covers the case where the scheduler itself
stops firing.

Every stage is individually wrapped. One dropped connection, one malformed
tick, one bad symbol degrades that stage and the cycle carries on; it never
takes the process down.
"""

from __future__ import annotations

import logging
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone

from ..brokers.base import AccountSnapshot, Broker, BrokerError
from ..news.calendar import NewsDetector, NewsWindow
from ..risk.journal import TradeJournal
from ..risk.limits import RiskManager
from ..strategy.base import Strategy, StrategyContext
from . import hours

log = logging.getLogger("tradebot.cycle")


@dataclass
class CycleReport:
    """What happened during one pass. Logged and returned for the watchdog."""

    started_at: datetime
    finished_at: datetime | None = None
    symbols_checked: list[str] = field(default_factory=list)
    symbols_skipped: dict[str, str] = field(default_factory=dict)
    orders_submitted: int = 0
    errors: list[str] = field(default_factory=list)
    equity: float | None = None
    halted: bool = False
    halt_reason: str = ""
    reconciliation_ok: bool | None = None

    @property
    def ok(self) -> bool:
        return not self.errors

    def summary(self) -> str:
        span = ""
        if self.finished_at:
            span = f" in {(self.finished_at - self.started_at).total_seconds():.2f}s"
        return (
            f"cycle{span}: checked={len(self.symbols_checked)} "
            f"skipped={len(self.symbols_skipped)} orders={self.orders_submitted} "
            f"errors={len(self.errors)} halted={self.halted}"
        )


class TradingCycle:
    """Runs one pass: refresh state, evaluate each symbol, act, reconcile."""

    def __init__(
        self,
        broker: Broker,
        strategy: Strategy,
        risk: RiskManager,
        journal: TradeJournal,
        symbols: list[str],
        news: NewsDetector | None = None,
        reconcile_every: int = 20,
    ) -> None:
        self.broker = broker
        self.strategy = strategy
        self.risk = risk
        self.journal = journal
        self.symbols = symbols
        self.news = news
        self.reconcile_every = reconcile_every
        self._cycles = 0

    # -- entry point -----------------------------------------------------

    def run_once(self, now: datetime | None = None) -> CycleReport:
        """Execute one full cycle. Never raises; failures land in the report."""
        now = now or datetime.now(timezone.utc)
        report = CycleReport(started_at=now)
        self._cycles += 1

        account = self._guard(report, "account", self._fetch_account)
        if account is None:
            report.finished_at = datetime.now(timezone.utc)
            return report

        report.equity = account.equity
        # First contact with the account writes the reconciliation baseline.
        # A no-op every cycle after the first, wherever the journal persists.
        self._guard(report, "baseline",
                    lambda: self.journal.ensure_baseline(account.balance))
        self._guard(report, "risk-update", lambda: self.risk.update_equity(account.equity, now))
        report.halted = self.risk.state.halted
        report.halt_reason = self.risk.state.halt_reason

        positions = self._guard(report, "positions", self.broker.get_positions) or []

        for symbol in self.symbols:
            self._guard(
                report,
                f"symbol:{symbol}",
                lambda s=symbol: self._process_symbol(s, account, positions, report, now),
            )

        # On the first cycle of the process, then every reconcile_every after.
        # The old `% == 0` never fired on a host that runs one cycle per
        # process -- which is exactly how the cloud runs it, so the money
        # cross-check silently never happened where it mattered most.
        if self._cycles % self.reconcile_every == 1 or self.reconcile_every == 1:
            self._guard(report, "reconcile", lambda: self._reconcile(account, report))

        report.finished_at = datetime.now(timezone.utc)
        log.info(report.summary())
        return report

    # -- stages ----------------------------------------------------------

    def _fetch_account(self) -> AccountSnapshot:
        if not self.broker.is_connected:
            self.broker.connect()
        return self.broker.get_account()

    def _process_symbol(
        self,
        symbol: str,
        account: AccountSnapshot,
        positions: list,
        report: CycleReport,
        now: datetime,
    ) -> None:
        session = hours.is_tradable(symbol, now)
        if not session.is_open:
            report.symbols_skipped[symbol] = session.reason
            return

        news_window: NewsWindow | None = None
        if self.news is not None:
            # Checked every cycle, not once a day — that is the whole point.
            news_window = self.news.check(symbol, now)

        instrument = self.broker.get_instrument(symbol)
        candles = self.broker.get_candles(symbol, self.strategy.timeframe, self.strategy.lookback)
        bid, ask = self.broker.get_price(symbol)

        context = StrategyContext(
            symbol=symbol,
            instrument=instrument,
            candles=candles,
            bid=bid,
            ask=ask,
            account=account,
            open_positions=[p for p in positions if p.symbol == symbol],
            news=news_window,
            risk=self.risk,
            now=now,
        )

        report.symbols_checked.append(symbol)
        actions = self.strategy.evaluate(context)
        for action in actions or []:
            if action.execute(self.broker, self.risk, self.journal, context):
                report.orders_submitted += 1

    def _reconcile(self, account: AccountSnapshot, report: CycleReport) -> None:
        """Cross-check the journal against the broker's own balance."""
        result = self.journal.reconcile(account.balance)
        report.reconciliation_ok = result.matches
        if result.matches:
            log.debug("reconciliation %s", result.describe())
        else:
            # Loud on purpose: a drift here means the money maths is wrong.
            log.error("RECONCILIATION MISMATCH %s", result.describe())

    # -- error isolation -------------------------------------------------

    def _guard(self, report: CycleReport, stage: str, fn):
        """Run one stage, recording any failure instead of propagating it."""
        try:
            return fn()
        except BrokerError as err:
            report.errors.append(f"{stage}: broker: {err}")
            log.warning("stage %s failed (broker): %s", stage, err)
        except Exception as err:  # noqa: BLE001 - deliberate catch-all
            report.errors.append(f"{stage}: {type(err).__name__}: {err}")
            log.error("stage %s failed: %s\n%s", stage, err, traceback.format_exc())
        return None
