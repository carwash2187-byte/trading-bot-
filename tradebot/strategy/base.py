"""Strategy interface — deliberately empty of trading logic.

This file defines the *shape* a strategy must have and the actions it may
request. It contains no entry rules, no exit rules, no indicator thresholds and
no opinion about news. Plug your own logic in by subclassing :class:`Strategy`.

The split matters: actions are *requested* by the strategy and *executed* by
the framework, which is what lets sizing, circuit breakers and journalling be
applied uniformly no matter what logic sits on top.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from datetime import datetime

from ..brokers.base import (
    AccountSnapshot,
    BracketOrder,
    Broker,
    BrokerError,
    Candle,
    OrderSide,
    Position,
)
from ..instruments import Instrument
from ..news.calendar import NewsWindow
from ..risk.journal import TradeJournal
from ..risk.limits import RiskManager
from ..risk.sizing import size_position


@dataclass
class StrategyContext:
    """Everything a strategy is given for one symbol on one cycle."""

    symbol: str
    instrument: Instrument
    candles: list[Candle]
    bid: float
    ask: float
    account: AccountSnapshot
    open_positions: list[Position]
    news: NewsWindow | None
    risk: RiskManager
    now: datetime

    @property
    def mid(self) -> float:
        return (self.bid + self.ask) / 2.0

    @property
    def last_close(self) -> float | None:
        return self.candles[-1].close if self.candles else None

    @property
    def has_position(self) -> bool:
        return bool(self.open_positions)


class Action(abc.ABC):
    """Something the strategy wants done."""

    @abc.abstractmethod
    def execute(
        self,
        broker: Broker,
        risk: RiskManager,
        journal: TradeJournal,
        context: StrategyContext,
    ) -> bool:
        """Perform the action. Returns True if an order actually went through."""


@dataclass
class Enter(Action):
    """Open a position, sized by the risk layer and protected by a bracket.

    The strategy supplies direction and price levels; it never supplies a lot
    size. Sizing is the framework's job so risk-per-trade and the contract
    multiplier are applied consistently.
    """

    side: OrderSide
    stop_loss: float
    take_profit: float | None = None
    risk_pct: float | None = None       # defaults to the configured limit
    comment: str = ""
    quote_to_account_rate: float = 1.0

    def execute(
        self,
        broker: Broker,
        risk: RiskManager,
        journal: TradeJournal,
        context: StrategyContext,
    ) -> bool:
        groups = {p.symbol: broker.get_instrument(p.symbol).correlation_group
                  for p in broker.get_positions()}
        decision = risk.check_entry(
            equity=context.account.equity,
            symbol=context.symbol,
            correlation_group=context.instrument.correlation_group,
            open_positions=broker.get_positions(),
            groups=groups,
        )
        if not decision.allowed:
            return False

        entry_price = context.ask if self.side.is_long else context.bid
        sized = size_position(
            instrument=context.instrument,
            equity=context.account.equity,
            risk_pct=self.risk_pct or risk.limits.risk_per_trade,
            entry_price=entry_price,
            stop_price=self.stop_loss,
            quote_to_account_rate=self.quote_to_account_rate,
        )
        if not sized.tradable:
            return False

        order = BracketOrder(
            symbol=context.symbol,
            side=self.side,
            lots=sized.lots,
            stop_loss=self.stop_loss,
            take_profit=self.take_profit,
            comment=self.comment,
        )
        try:
            broker.submit_bracket(order)
        except BrokerError:
            return False
        return True


@dataclass
class Exit(Action):
    """Close an open position and write the result to the journal."""

    ticket: str
    lots: float | None = None
    reason: str = ""

    def execute(
        self,
        broker: Broker,
        risk: RiskManager,
        journal: TradeJournal,
        context: StrategyContext,
    ) -> bool:
        position = broker.get_position(self.ticket)
        if position is None:
            return False
        try:
            fill = broker.close_position(self.ticket, self.lots)
        except BrokerError:
            return False

        pnl = context.instrument.pnl_in_account(
            position.entry_price, fill.price, fill.lots, position.is_long
        )
        journal.record_close(
            ticket=self.ticket,
            symbol=position.symbol,
            side=position.side,
            lots=fill.lots,
            entry_price=position.entry_price,
            exit_price=fill.price,
            realized_pnl=pnl,
            opened_at=position.opened_at,
            closed_at=fill.filled_at,
            reason=self.reason,
        )
        return True


@dataclass
class AdjustStop(Action):
    """Move the server-side stop, e.g. to trail it or lock in breakeven."""

    ticket: str
    stop_loss: float | None = None
    take_profit: float | None = None

    def execute(
        self,
        broker: Broker,
        risk: RiskManager,
        journal: TradeJournal,
        context: StrategyContext,
    ) -> bool:
        try:
            broker.modify_protection(self.ticket, self.stop_loss, self.take_profit)
        except BrokerError:
            return False
        return True


class Strategy(abc.ABC):
    """Subclass this and implement :meth:`evaluate`. Nothing else is required.

    Attributes:
        timeframe: Which candle series the cycle should fetch, e.g. ``"1h"``.
        lookback: How many bars of history to hand over each cycle.
    """

    timeframe: str = "1h"
    lookback: int = 300
    name: str = "unnamed"

    @abc.abstractmethod
    def evaluate(self, context: StrategyContext) -> list[Action]:
        """Return the actions to take for this symbol on this cycle.

        Return an empty list to do nothing. This method must not place orders
        itself — returning actions is what keeps risk and journalling in the
        loop.
        """


class NoOpStrategy(Strategy):
    """A strategy that never trades.

    Ships as the default so the whole pipeline — connection, data, risk,
    journal, reconciliation — can be exercised end to end before any real
    logic exists.
    """

    name = "noop"

    def evaluate(self, context: StrategyContext) -> list[Action]:
        return []
