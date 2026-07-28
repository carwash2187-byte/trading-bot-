"""tradebot — broker-agnostic trading infrastructure.

Deliberately contains no strategy logic. Subclass
:class:`tradebot.strategy.base.Strategy` and plug it into
:class:`tradebot.runtime.cycle.TradingCycle`; sizing, circuit breakers,
journalling and reliability then apply to it automatically.

Everything defaults to paper trading. See ``README.md`` for the live-mode gate.
"""

from __future__ import annotations

__version__ = "1.0.0"

from .brokers.base import (
    AccountSnapshot,
    BracketOrder,
    Broker,
    BrokerError,
    Candle,
    Fill,
    LiveModeRefused,
    OrderSide,
    OrderType,
    Position,
    TradingMode,
)
from .brokers.paper import PaperBroker
from .instruments import Instrument, InstrumentError, get_instrument
from .risk.journal import JournalEntry, Reconciliation, TradeJournal
from .risk.limits import RiskDecision, RiskLimits, RiskManager, RiskState
from .risk.sizing import SizedTrade, SizingError, size_position
from .runtime.cycle import CycleReport, TradingCycle
from .runtime.lock import AlreadyRunning, InstanceLock
from .runtime.state import StateStore
from .strategy.base import (
    Action,
    AdjustStop,
    Enter,
    Exit,
    NoOpStrategy,
    Strategy,
    StrategyContext,
)

__all__ = [
    "__version__",
    # brokers
    "Broker", "BrokerError", "LiveModeRefused", "TradingMode", "PaperBroker",
    "BracketOrder", "OrderSide", "OrderType", "Position", "Fill",
    "AccountSnapshot", "Candle",
    # instruments and money
    "Instrument", "InstrumentError", "get_instrument",
    "size_position", "SizedTrade", "SizingError",
    # risk
    "RiskManager", "RiskLimits", "RiskState", "RiskDecision",
    "TradeJournal", "JournalEntry", "Reconciliation",
    # runtime
    "TradingCycle", "CycleReport", "InstanceLock", "AlreadyRunning", "StateStore",
    # strategy
    "Strategy", "StrategyContext", "NoOpStrategy",
    "Action", "Enter", "Exit", "AdjustStop",
]
