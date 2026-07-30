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
import logging
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

log = logging.getLogger("tradebot.strategy")


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

    The strategy supplies direction and price levels, and sizing is normally the
    framework's job so risk-per-trade and the contract multiplier are applied
    consistently. A strategy may override that with ``lots`` when the method it
    copies sizes trades a different way -- see the field comment.
    """

    side: OrderSide
    stop_loss: float
    take_profit: float | None = None
    risk_pct: float | None = None       # defaults to the configured limit
    comment: str = ""
    # Overrides the instrument's own rate when set to anything but 1.0. Normally
    # left alone: the conversion is a property of the contract, so it lives on
    # the Instrument and strategies should not have to know about it.
    quote_to_account_rate: float = 1.0
    # A fixed lot size, instead of one derived from a risk percentage.
    #
    # This is how MambaFX keeps a losing trade barely visible: "if you're using a
    # 0.01 that would have been a dollar sixty loss for a five dollar and 10 cent
    # gain". Under percentage sizing a tighter stop simply buys more lots and the
    # cash loss is unchanged -- 2% is 2% whether the stop is 10 pips or 100. His
    # small losses come from a small FIXED lot meeting a tight stop; it takes both
    # together. On $150 at 0.01 lots a 16-pip stop costs 1.07% and a 10-pip stop
    # 0.67%, against a flat 2% at any stop width.
    #
    # Still capped by free margin, so it cannot ask for a size the account cannot
    # carry.
    lots: float | None = None

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

        # HIS STOP, MADE LEGAL AT THE BROKER. His rule puts the stop on the
        # trigger candle's own extreme -- "that last candle where we broke, the
        # high of that candle" -- and when that candle is small the stop lands a
        # few points from price. That is a perfectly good stop on a chart and an
        # UNFILLABLE ORDER on a real account: MT5 rejects it outright as invalid
        # stops. Measured on his own US30 signals, one stop in this build came
        # out 3.0 points wide, which most brokers refuse.
        #
        # Pushing it out to the broker's published floor is the smallest possible
        # change that still places his trade, and the number is the broker's
        # rather than mine. Refusing the trade instead would be me overruling him
        # over a platform limit he never has to think about.
        floor = context.instrument.min_stop_distance
        if floor > 0 and abs(entry_price - self.stop_loss) < floor:
            widened = (entry_price - floor if self.side.is_long
                       else entry_price + floor)
            log.info("%s stop %.5f is inside the broker's %.5f minimum; "
                     "moved to %.5f so the order is accepted",
                     context.symbol, self.stop_loss, floor, widened)
            self.stop_loss = widened

        # Cap the size at what free margin can actually carry, with a tenth
        # held back for the position moving against us before the stop. The
        # risk formula alone can balloon when volatility collapses -- risk
        # divided by a tiny stop distance is a huge position -- and the right
        # response is to trade the affordable size, not to ask the broker for
        # an impossible one and treat its refusal as an emergency.
        # The notional has to be in the ACCOUNT's currency before it is compared
        # against the account's free margin. Skipping that conversion is the same
        # bug as skipping it in the sizer, and it bites harder: on GBPJPY one lot
        # is 21.6 MILLION yen, which measured against dollars of margin caps the
        # position at 0.0003 lots and refuses every trade on the pair. It cost
        # this project 14 valid setups and looked exactly like having no signal.
        rate = (
            self.quote_to_account_rate
            if self.quote_to_account_rate != 1.0
            else context.instrument.quote_to_account_rate
        )
        notional_per_lot = entry_price * context.instrument.contract_size * rate
        affordable = 0.0
        if notional_per_lot > 0:
            affordable = (
                context.account.margin_free * risk.limits.leverage * 0.9
                / notional_per_lot
            )

        if self.lots is not None:
            lots = context.instrument.round_lots(min(self.lots, affordable)
                                                 if affordable > 0 else self.lots)
            if lots < context.instrument.min_lot:
                return False
        else:
            sized = size_position(
                instrument=context.instrument,
                equity=context.account.equity,
                risk_pct=self.risk_pct or risk.limits.risk_per_trade,
                entry_price=entry_price,
                stop_price=self.stop_loss,
                quote_to_account_rate=rate,
                max_lots=affordable,
            )
            if not sized.tradable:
                # Loudly. A silent refusal looks identical to having no signal,
                # which is how a broken currency conversion hid on every
                # yen-quoted pair for the life of this project.
                log.warning("size refused for %s: %s", self.comment or "?",
                            sized.reason or "no reason given")
                return False
            lots = sized.lots

        order = BracketOrder(
            symbol=context.symbol,
            side=self.side,
            lots=lots,
            stop_loss=self.stop_loss,
            take_profit=self.take_profit,
            comment=self.comment,
        )
        # A rejection is NOT swallowed. Silently returning False here made a
        # bot whose every order bounces indistinguishable from a bot with no
        # signal -- green runs, empty account, nothing to investigate. Letting
        # it propagate lands it in the cycle's error report, which fails the
        # run, which is what wakes the self-repair chain and, if it keeps
        # happening, the human. Refusals by the risk layer still return False
        # above: being told "no" is a decision, not a failure.
        broker.submit_bracket(order)
        # Count it against today, so per-day caps survive the trade closing.
        risk.record_entry(self.comment or "")
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
        # Propagates on failure for the same reason Enter does: an exit that
        # silently fails leaves a position running with nobody the wiser.
        fill = broker.close_position(self.ticket, self.lots)

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
            # Entries stamp the owning strategy into the order comment, so the
            # broker's own record of the position tells us who to credit or
            # blame. Nothing extra has to be persisted or kept in sync.
            strategy=position.comment,
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
        broker.modify_protection(self.ticket, self.stop_loss, self.take_profit)
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
