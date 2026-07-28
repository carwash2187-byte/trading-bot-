"""Run a real strategy over real bars and report what it would have done.

This drives the *same* :class:`~tradebot.strategy.base.Strategy` objects, the
same ``Enter``/``Exit``/``AdjustStop`` actions and the same position sizing that
run against a live broker. That is the whole point: a backtest of a rewritten
copy of a strategy measures the copy, and every previous test in this project
measured Pine Script that the bot does not run.

Two things decide whether a backtest tells the truth, and both are easy to get
wrong in the flattering direction:

**Stops are checked against each bar's high and low, not its close.** Checking
only closes means a trade whose stop was blown through mid-bar appears to
survive to a happier price. That single shortcut can turn a losing strategy into
a winning chart, and it is invisible unless you look for it.

**Costs are charged on every fill.** A fee of zero is the most common way a
published backtest lies. Crossing the spread and paying the taker fee is
subtracted from real money here, in full, on entry and on exit.

Where the order of events inside a bar is unknowable, the pessimistic reading
wins -- the adverse extreme is assumed to have come first.
"""

from __future__ import annotations

import logging
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from ..brokers.base import BrokerError, Candle, Fill, TradingMode
from ..brokers.paper import PaperBroker
from ..instruments import Instrument
from ..news.calendar import NewsWindow
from ..risk.journal import TradeJournal
from ..risk.limits import RiskLimits, RiskManager
from ..strategy.base import Strategy, StrategyContext

log = logging.getLogger("tradebot.backtest")


class BacktestBroker(PaperBroker):
    """A paper broker that charges realistic costs and honours intrabar stops.

    Args:
        spread_pct: full quoted spread as a fraction of price. The default
            0.104% is what Leo's own TradeLocker screen showed on BTCUSD; a
            fixed cash spread would be meaningless across a window where BTC
            ranges from $3,800 to $73,000.
        fee_pct: taker fee per side, as a fraction of notional.
    """

    def __init__(
        self,
        starting_balance: float = 20_000.0,
        spread_pct: float = 0.00104,
        fee_pct: float = 0.00055,
        **kwargs,
    ) -> None:
        super().__init__(starting_balance=starting_balance,
                         mode=TradingMode.PAPER, **kwargs)
        self.spread_pct = spread_pct
        self.fee_pct = fee_pct
        self.fees_paid = 0.0
        # Entry fees are charged when the position opens but only become
        # attributable when it closes. Held here so the per-trade P&L and the
        # account balance cannot drift apart.
        self._entry_fees: dict[str, float] = {}

    # -- pricing ---------------------------------------------------------

    def get_price(self, symbol: str) -> tuple[float, float]:
        key = symbol.upper()
        if key not in self._prices:
            raise BrokerError(f"no price for {symbol}")
        mid = self._prices[key]
        half = mid * self.spread_pct / 2.0
        return (mid - half, mid + half)

    def advance(self, symbol: str, candle: Candle) -> None:
        """Walk price through one bar so stops fire where they really would.

        The true path inside a bar is unknown, so the adverse extreme is
        assumed to come first: for a long, the low is tested before the high.
        Anything else quietly credits the strategy with a target it might never
        have reached alive.
        """
        longs = any(p.symbol == symbol.upper() and p.is_long
                    for p in self._positions.values())
        first, second = (candle.low, candle.high) if longs else (candle.high, candle.low)
        self.set_price(symbol, first)
        self.set_price(symbol, second)
        self.set_price(symbol, candle.close)

    # -- costs -----------------------------------------------------------

    def _charge(self, symbol: str, price: float, lots: float) -> float:
        notional = abs(price * lots * self.get_instrument(symbol).contract_size)
        fee = notional * self.fee_pct
        self.balance -= fee
        self.fees_paid += fee
        return fee

    def submit_bracket(self, order):
        fill = super().submit_bracket(order)
        self._entry_fees[fill.ticket] = self._charge(
            fill.symbol, fill.price, fill.lots
        )
        return fill

    def _settle(self, ticket, exit_price, lots, reason) -> Fill:
        opened = self._positions[ticket].lots
        entry_fee = self._entry_fees.get(ticket, 0.0)

        fill = super()._settle(ticket, exit_price, lots, reason)
        exit_fee = self._charge(fill.symbol, fill.price, fill.lots)

        # Charge the share of the entry fee belonging to the lots just closed,
        # so a partial exit does not carry the whole cost of opening.
        share = entry_fee * (fill.lots / opened) if opened else entry_fee
        self._entry_fees[ticket] = entry_fee - share
        if ticket not in self._positions:
            self._entry_fees.pop(ticket, None)

        # A trade's recorded P&L must be what it actually netted. If these
        # disagree with the balance, one of the two numbers is a lie and there
        # is no way to tell which from the report.
        if self.closed_trades:
            self.closed_trades[-1]["pnl"] -= exit_fee + share
            self.closed_trades[-1]["fee"] = exit_fee + share
        return fill


@dataclass
class BacktestResult:
    """What a strategy did, in the terms that decide whether to trade it."""

    strategy: str
    symbol: str
    timeframe: str
    start: datetime | None
    end: datetime | None
    starting_balance: float
    ending_balance: float
    trades: list[dict] = field(default_factory=list)
    equity_curve: list[tuple[datetime, float]] = field(default_factory=list)
    fees_paid: float = 0.0

    @property
    def net_profit(self) -> float:
        return self.ending_balance - self.starting_balance

    @property
    def return_pct(self) -> float:
        return 100.0 * self.net_profit / self.starting_balance

    @property
    def wins(self) -> list[dict]:
        return [t for t in self.trades if t["pnl"] > 0]

    @property
    def losses(self) -> list[dict]:
        return [t for t in self.trades if t["pnl"] <= 0]

    @property
    def win_rate(self) -> float:
        return 100.0 * len(self.wins) / len(self.trades) if self.trades else 0.0

    @property
    def profit_factor(self) -> float:
        """Gross profit over gross loss. Below 1.0 means it loses money."""
        gross_win = sum(t["pnl"] for t in self.wins)
        gross_loss = abs(sum(t["pnl"] for t in self.losses))
        if gross_loss == 0:
            return float("inf") if gross_win > 0 else 0.0
        return gross_win / gross_loss

    @property
    def avg_win(self) -> float:
        return sum(t["pnl"] for t in self.wins) / len(self.wins) if self.wins else 0.0

    @property
    def avg_loss(self) -> float:
        return (
            sum(t["pnl"] for t in self.losses) / len(self.losses)
            if self.losses else 0.0
        )

    @property
    def max_drawdown_pct(self) -> float:
        """Worst peak-to-trough fall in equity. This is what kills accounts."""
        peak = self.starting_balance
        worst = 0.0
        for _, equity in self.equity_curve:
            peak = max(peak, equity)
            if peak > 0:
                worst = max(worst, 100.0 * (peak - equity) / peak)
        return worst

    @property
    def days(self) -> float:
        if not self.start or not self.end:
            return 0.0
        return max((self.end - self.start).total_seconds() / 86400.0, 1.0)

    @property
    def per_day(self) -> float:
        return self.net_profit / self.days if self.days else 0.0

    @property
    def per_week(self) -> float:
        return self.per_day * 7.0

    def summary(self) -> str:
        return "\n".join(
            [
                f"{self.strategy} on {self.symbol} {self.timeframe}"
                f"  ({self.days:.0f} days)",
                f"  net           ${self.net_profit:+,.0f}  "
                f"({self.return_pct:+.1f}%)  from ${self.starting_balance:,.0f}",
                f"  per week      ${self.per_week:+,.0f}",
                f"  trades        {len(self.trades)}  "
                f"({self.win_rate:.1f}% won)",
                f"  avg win/loss  ${self.avg_win:+,.0f} / ${self.avg_loss:+,.0f}",
                f"  profit factor {self.profit_factor:.2f}",
                f"  max drawdown  {self.max_drawdown_pct:.1f}%",
                f"  fees paid     ${self.fees_paid:,.0f}",
            ]
        )


def run_backtest(
    strategy: Strategy,
    candles: list[Candle],
    symbol: str = "BTCUSD",
    timeframe: str = "2h",
    starting_balance: float = 20_000.0,
    risk_per_trade: float = 0.01,
    spread_pct: float = 0.00104,
    fee_pct: float = 0.00055,
    instrument: Instrument | None = None,
    warmup: int | None = None,
) -> BacktestResult:
    """Replay ``candles`` through ``strategy`` and report the outcome.

    Args:
        risk_per_trade: fraction of equity risked per trade, applied by the
            same sizing code the live bot uses.
        warmup: bars to feed before trading is allowed. Defaults to the
            strategy's own ``lookback`` so its indicators are warm.
    """
    broker = BacktestBroker(
        starting_balance=starting_balance,
        spread_pct=spread_pct,
        fee_pct=fee_pct,
    )
    broker.connect()
    if instrument is not None:
        broker.register_instrument(instrument)

    journal = TradeJournal(Path(tempfile.mkdtemp()) / "backtest.jsonl")
    risk = RiskManager(RiskLimits(
        risk_per_trade=risk_per_trade,
        # The strategy under test is the subject, so the circuit breakers are
        # opened as wide as they go. Leaving them at live settings would report
        # on the limiter tripping rather than on the strategy itself -- worth
        # measuring, but as a separate question.
        daily_loss_limit=0.98,
        max_drawdown_limit=0.99,
    ))
    inst = instrument or broker.get_instrument(symbol)

    window = getattr(strategy, "lookback", 300)
    warmup = warmup if warmup is not None else window
    equity_curve: list[tuple[datetime, float]] = []

    for i, candle in enumerate(candles):
        # Settle first: this bar's range applies to positions already open.
        if broker._prices.get(symbol.upper()) is not None:
            broker.advance(symbol, candle)
        else:
            broker.set_price(symbol, candle.close)

        equity_curve.append((candle.timestamp, broker.get_account().equity))
        if i < warmup:
            broker.set_price(symbol, candle.close)
            continue

        bid, ask = broker.get_price(symbol)
        context = StrategyContext(
            symbol=symbol,
            instrument=inst,
            # Only closed bars, up to and including this one -- slicing here
            # is what stops the strategy seeing its own future. The window is
            # also capped at the strategy's own lookback, which is not merely
            # a speed fix: live, the bot asks the broker for exactly that many
            # bars, so handing the backtest all of history would test a
            # strategy with more context than it will ever have.
            candles=candles[max(0, i + 1 - window) : i + 1],
            bid=bid,
            ask=ask,
            account=broker.get_account(),
            open_positions=[p for p in broker.get_positions()
                            if p.symbol == symbol.upper()],
            news=None,
            risk=risk,
            now=candle.timestamp,
        )

        try:
            actions = strategy.evaluate(context)
        except Exception:
            log.exception("%s blew up on bar %d", strategy.name, i)
            continue

        for action in actions:
            try:
                action.execute(broker, risk, journal, context)
            except BrokerError:
                continue        # a rejected order is a normal outcome

    # Close anything still open at the last price, so the result is a complete
    # accounting rather than one flattered by an open winner.
    for position in list(broker.get_positions()):
        try:
            broker.close_position(position.ticket)
        except BrokerError:
            pass

    if candles:
        equity_curve.append((candles[-1].timestamp, broker.get_account().equity))

    return BacktestResult(
        strategy=getattr(strategy, "name", type(strategy).__name__),
        symbol=symbol,
        timeframe=timeframe,
        start=candles[0].timestamp if candles else None,
        end=candles[-1].timestamp if candles else None,
        starting_balance=starting_balance,
        ending_balance=broker.balance,
        trades=list(broker.closed_trades),
        equity_curve=equity_curve,
        fees_paid=broker.fees_paid,
    )
