"""Broker abstraction: one interface, three implementations.

Strategy code talks only to :class:`Broker`. Swapping MetaTrader5 for
TradeLocker or the paper simulator must not require touching a single line of
strategy logic.

Two safety rules are enforced here rather than left to each adapter:

1. Every broker starts in paper/demo mode. Live trading requires passing
   ``mode=TradingMode.LIVE`` *and* setting the ``TRADEBOT_ALLOW_LIVE=yes``
   environment variable. A config typo alone cannot arm it, and the live flag
   is never written to any state file, so a restart always lands in paper.
2. Entries submit a bracket (stop-loss and take-profit attached to the entry
   order) so the broker holds the protection server-side. If this process dies
   mid-trade the position is still guarded.
"""

from __future__ import annotations

import abc
import enum
import os
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from ..instruments import Instrument


class TradingMode(enum.Enum):
    """Where orders actually go."""

    PAPER = "paper"
    DEMO = "demo"
    LIVE = "live"


class OrderSide(enum.Enum):
    BUY = "buy"
    SELL = "sell"

    @property
    def is_long(self) -> bool:
        return self is OrderSide.BUY

    @property
    def opposite(self) -> "OrderSide":
        return OrderSide.SELL if self is OrderSide.BUY else OrderSide.BUY


class OrderType(enum.Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"


class BrokerError(RuntimeError):
    """Any broker-side failure. Callers retry on the next cycle."""


class LiveModeRefused(BrokerError):
    """Raised when live trading was requested without the explicit opt-in."""


LIVE_ENV_VAR = "TRADEBOT_ALLOW_LIVE"
LIVE_ENV_VALUE = "yes"


@dataclass(frozen=True)
class BracketOrder:
    """An entry with its protection attached, submitted as one instruction.

    ``stop_loss`` is required. An entry without a server-side stop is exactly
    the failure mode this class exists to prevent, so it is not optional.
    """

    symbol: str
    side: OrderSide
    lots: float
    stop_loss: float
    take_profit: float | None = None
    order_type: OrderType = OrderType.MARKET
    limit_price: float | None = None
    comment: str = ""
    client_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])

    def __post_init__(self) -> None:
        if self.lots <= 0:
            raise ValueError("lots must be > 0")
        if self.stop_loss <= 0:
            raise ValueError("stop_loss is required and must be a real price")
        if self.order_type in (OrderType.LIMIT, OrderType.STOP) and self.limit_price is None:
            raise ValueError(f"{self.order_type.value} order needs limit_price")
        # A stop on the wrong side of the entry would trigger instantly.
        if self.limit_price is not None:
            if self.side.is_long and self.stop_loss >= self.limit_price:
                raise ValueError("long stop_loss must sit below the entry price")
            if not self.side.is_long and self.stop_loss <= self.limit_price:
                raise ValueError("short stop_loss must sit above the entry price")


@dataclass
class Position:
    """An open position as the broker currently reports it."""

    ticket: str
    symbol: str
    side: OrderSide
    lots: float
    entry_price: float
    stop_loss: float | None
    take_profit: float | None
    opened_at: datetime
    unrealized_pnl: float = 0.0
    comment: str = ""

    @property
    def is_long(self) -> bool:
        return self.side.is_long


@dataclass
class Fill:
    """Confirmation that an order executed."""

    ticket: str
    client_id: str
    symbol: str
    side: OrderSide
    lots: float
    price: float
    filled_at: datetime
    commission: float = 0.0
    stop_loss: float | None = None
    take_profit: float | None = None


@dataclass
class AccountSnapshot:
    """Account state as the broker reports it, for journal reconciliation."""

    balance: float
    equity: float
    currency: str
    margin_used: float = 0.0
    margin_free: float = 0.0
    taken_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class Candle:
    """One OHLC bar."""

    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0


class Broker(abc.ABC):
    """The single interface every strategy and risk component codes against."""

    def __init__(self, mode: TradingMode = TradingMode.PAPER, **_: object) -> None:
        self._mode = self._authorize(mode)
        self._connected = False

    # -- live-mode gate --------------------------------------------------

    @staticmethod
    def _authorize(mode: TradingMode) -> TradingMode:
        """Refuse live mode unless the operator opted in out-of-band.

        Requiring an environment variable means a bad config file, a bad
        default, or a restart can never silently arm real money — someone has
        to set it in the launching shell on purpose.
        """
        if mode is not TradingMode.LIVE:
            return mode
        if os.environ.get(LIVE_ENV_VAR, "").strip().lower() != LIVE_ENV_VALUE:
            raise LiveModeRefused(
                "LIVE trading requested but not authorized. "
                f"Set {LIVE_ENV_VAR}={LIVE_ENV_VALUE} in the environment that "
                "launches the bot. This is deliberately not settable from a "
                "config file."
            )
        return TradingMode.LIVE

    @property
    def mode(self) -> TradingMode:
        return self._mode

    @property
    def is_live(self) -> bool:
        return self._mode is TradingMode.LIVE

    @property
    def is_connected(self) -> bool:
        return self._connected

    # -- lifecycle -------------------------------------------------------

    @abc.abstractmethod
    def connect(self) -> None:
        """Open the broker session. Must be idempotent."""

    @abc.abstractmethod
    def disconnect(self) -> None:
        """Close the session. Must be safe to call when already closed."""

    def __enter__(self) -> "Broker":
        self.connect()
        return self

    def __exit__(self, *exc: object) -> None:
        self.disconnect()

    # -- market data -----------------------------------------------------

    @abc.abstractmethod
    def get_instrument(self, symbol: str) -> Instrument:
        """Return contract details, ideally fetched live from the broker."""

    @abc.abstractmethod
    def get_price(self, symbol: str) -> tuple[float, float]:
        """Current ``(bid, ask)``."""

    @abc.abstractmethod
    def get_candles(
        self, symbol: str, timeframe: str, count: int, end: datetime | None = None
    ) -> list[Candle]:
        """Historical OHLC bars, oldest first."""

    # -- trading ---------------------------------------------------------

    @abc.abstractmethod
    def submit_bracket(self, order: BracketOrder) -> Fill:
        """Submit an entry with server-side stop-loss and take-profit."""

    @abc.abstractmethod
    def close_position(self, ticket: str, lots: float | None = None) -> Fill:
        """Close all or part of a position."""

    @abc.abstractmethod
    def modify_protection(
        self, ticket: str, stop_loss: float | None = None, take_profit: float | None = None
    ) -> None:
        """Move the server-side stop and/or target on an open position."""

    @abc.abstractmethod
    def get_positions(self) -> list[Position]:
        """All positions currently open on the account."""

    @abc.abstractmethod
    def get_account(self) -> AccountSnapshot:
        """Balance and equity, used to reconcile against the local journal."""

    # -- helpers ---------------------------------------------------------

    def get_position(self, ticket: str) -> Position | None:
        for pos in self.get_positions():
            if pos.ticket == ticket:
                return pos
        return None

    def close_all(self) -> list[Fill]:
        """Flatten everything. Used by circuit breakers and shutdown."""
        fills = []
        for pos in self.get_positions():
            try:
                fills.append(self.close_position(pos.ticket))
            except BrokerError:
                # Keep going; one stuck position must not strand the others.
                continue
        return fills

    def describe(self) -> str:
        return f"{type(self).__name__}(mode={self._mode.value}, connected={self._connected})"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def retry(fn, attempts: int = 3, delay: float = 0.5, exc: type[Exception] = BrokerError):
    """Retry a flaky broker call a few times before giving up.

    Network hiccups are routine and must not end a cycle. Real failures still
    surface after the last attempt so the cycle handler can log them.
    """
    last: Exception | None = None
    for attempt in range(attempts):
        try:
            return fn()
        except exc as err:  # pragma: no cover - exercised via adapters
            last = err
            if attempt < attempts - 1:
                time.sleep(delay * (2**attempt))
    raise last  # type: ignore[misc]
