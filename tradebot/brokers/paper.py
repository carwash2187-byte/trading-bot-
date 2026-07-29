"""Local paper-trading simulator.

Implements the full :class:`Broker` interface with no network access, so the
same strategy and risk code can be exercised in tests, in backtests, and in a
dry run before anything points at a real account.

Bracket protection is honoured the way a real broker honours it: once a
position is open its stop and target live in the simulator, and they are
checked on every price update. Killing the "bot" does not remove them.
"""

from __future__ import annotations

import itertools
from datetime import datetime, timedelta, timezone

from ..instruments import Instrument, get_instrument
from .base import (
    AccountSnapshot,
    BracketOrder,
    Broker,
    BrokerError,
    Candle,
    Fill,
    OrderSide,
    OrderType,
    Position,
    TradingMode,
    utcnow,
)


class PaperBroker(Broker):
    """A deterministic in-memory broker.

    Args:
        starting_balance: Opening account balance.
        currency: Account currency.
        spread: Quoted spread in price units, applied around the mid price.
        commission_per_lot: Round-turn commission charged on entry.
        slippage: Adverse price movement applied to every market fill.
    """

    def __init__(
        self,
        starting_balance: float = 10_000.0,
        currency: str = "USD",
        spread: float = 0.0002,
        commission_per_lot: float = 0.0,
        slippage: float = 0.0,
        mode: TradingMode = TradingMode.PAPER,
    ) -> None:
        if mode is TradingMode.LIVE:
            raise BrokerError("PaperBroker cannot run in LIVE mode; use a real adapter")
        super().__init__(mode=mode)
        self.balance = starting_balance
        self.currency = currency
        self.spread = spread
        self.commission_per_lot = commission_per_lot
        self.slippage = slippage

        self._positions: dict[str, Position] = {}
        self._prices: dict[str, float] = {}          # symbol -> mid price
        self._candles: dict[tuple[str, str], list[Candle]] = {}
        self._instruments: dict[str, Instrument] = {}
        self._tickets = itertools.count(1)
        self.closed_trades: list[dict] = []          # simple audit trail

    # -- lifecycle -------------------------------------------------------

    def connect(self) -> None:
        self._connected = True

    def disconnect(self) -> None:
        self._connected = False

    # -- test/backtest fixtures -----------------------------------------

    def set_price(self, symbol: str, mid: float) -> None:
        """Set the current mid price and settle any triggered brackets."""
        self._prices[symbol.upper()] = mid
        self._check_brackets(symbol.upper(), mid)

    def feed_candles(self, symbol: str, timeframe: str, candles: list[Candle]) -> None:
        """Load history the simulator can serve back through get_candles()."""
        self._candles[(symbol.upper(), timeframe)] = list(candles)

    def register_instrument(self, inst: Instrument) -> None:
        self._instruments[inst.symbol.upper()] = inst

    # -- market data -----------------------------------------------------

    def get_instrument(self, symbol: str) -> Instrument:
        key = symbol.upper()
        if key in self._instruments:
            return self._instruments[key]
        return get_instrument(key)

    def get_price(self, symbol: str) -> tuple[float, float]:
        key = symbol.upper()
        if key not in self._prices:
            raise BrokerError(f"no simulated price for {symbol}; call set_price() first")
        mid = self._prices[key]
        half = self.spread / 2.0
        return (mid - half, mid + half)

    def get_candles(
        self, symbol: str, timeframe: str, count: int, end: datetime | None = None
    ) -> list[Candle]:
        rows = self._candles.get((symbol.upper(), timeframe), [])
        if end is not None:
            rows = [c for c in rows if c.timestamp <= end]
        return rows[-count:]

    # -- trading ---------------------------------------------------------

    def _stamp(self) -> datetime:
        """What time it is, as far as this broker is concerned.

        Live and paper trading both mean wall clock. The backtester overrides
        this to return the timestamp of the candle being replayed -- otherwise
        every simulated position is stamped with today's real date, and any
        rule that reasons about time (how long a trade has been held, how many
        trades happened today, whether this is still the same session) silently
        compares a 2025 candle against 2026. That does not crash; it just makes
        those rules do nothing, which is worse than crashing.
        """
        return utcnow()

    def submit_bracket(self, order: BracketOrder) -> Fill:
        if not self._connected:
            raise BrokerError("broker not connected")
        inst = self.get_instrument(order.symbol)
        lots = inst.round_lots(order.lots)
        if lots <= 0:
            raise BrokerError(
                f"{order.symbol}: size {order.lots} rounds below min lot {inst.min_lot}"
            )

        bid, ask = self.get_price(order.symbol)
        if order.order_type is OrderType.MARKET:
            price = ask + self.slippage if order.side.is_long else bid - self.slippage
        else:
            price = float(order.limit_price)  # type: ignore[arg-type]
        price = inst.round_price(price)

        # Reject a stop that is already through the fill price — a real broker
        # would either reject it or close the position instantly.
        if order.side.is_long and order.stop_loss >= price:
            raise BrokerError("long stop_loss is at or above the fill price")
        if not order.side.is_long and order.stop_loss <= price:
            raise BrokerError("short stop_loss is at or below the fill price")

        commission = self.commission_per_lot * lots
        self.balance -= commission

        ticket = f"P{next(self._tickets):06d}"
        self._positions[ticket] = Position(
            ticket=ticket,
            symbol=order.symbol.upper(),
            side=order.side,
            lots=lots,
            entry_price=price,
            stop_loss=inst.round_price(order.stop_loss),
            take_profit=inst.round_price(order.take_profit) if order.take_profit else None,
            opened_at=self._stamp(),
            comment=order.comment,
        )
        return Fill(
            ticket=ticket,
            client_id=order.client_id,
            symbol=order.symbol.upper(),
            side=order.side,
            lots=lots,
            price=price,
            filled_at=self._stamp(),
            commission=commission,
            stop_loss=order.stop_loss,
            take_profit=order.take_profit,
        )

    def close_position(self, ticket: str, lots: float | None = None) -> Fill:
        pos = self._positions.get(ticket)
        if pos is None:
            raise BrokerError(f"unknown ticket {ticket}")
        bid, ask = self.get_price(pos.symbol)
        exit_price = bid if pos.is_long else ask
        return self._settle(ticket, exit_price, lots, reason="manual")

    def modify_protection(
        self, ticket: str, stop_loss: float | None = None, take_profit: float | None = None
    ) -> None:
        pos = self._positions.get(ticket)
        if pos is None:
            raise BrokerError(f"unknown ticket {ticket}")
        inst = self.get_instrument(pos.symbol)
        if stop_loss is not None:
            pos.stop_loss = inst.round_price(stop_loss)
        if take_profit is not None:
            pos.take_profit = inst.round_price(take_profit)

    def get_positions(self) -> list[Position]:
        out = []
        for pos in self._positions.values():
            mid = self._prices.get(pos.symbol)
            if mid is not None:
                inst = self.get_instrument(pos.symbol)
                pos.unrealized_pnl = inst.pnl_in_account(
                    pos.entry_price, mid, pos.lots, pos.is_long
                )
            out.append(pos)
        return out

    def get_account(self) -> AccountSnapshot:
        unrealized = sum(p.unrealized_pnl for p in self.get_positions())
        equity = self.balance + unrealized
        return AccountSnapshot(
            balance=self.balance,
            equity=equity,
            currency=self.currency,
            # A simulator that does not model margin has all of its equity
            # free, not none of it. Defaulting this to zero told the
            # margin-aware position cap that nothing was affordable, and the
            # whole simulator silently stopped trading.
            margin_free=equity,
        )

    # -- internals -------------------------------------------------------

    def _check_brackets(self, symbol: str, mid: float) -> None:
        """Fire any stop or target the new price has crossed.

        Iterates over a snapshot because settling mutates the position dict.
        """
        for ticket, pos in list(self._positions.items()):
            if pos.symbol != symbol:
                continue
            if pos.is_long:
                if pos.stop_loss is not None and mid <= pos.stop_loss:
                    self._settle(ticket, pos.stop_loss, None, reason="stop_loss")
                elif pos.take_profit is not None and mid >= pos.take_profit:
                    self._settle(ticket, pos.take_profit, None, reason="take_profit")
            else:
                if pos.stop_loss is not None and mid >= pos.stop_loss:
                    self._settle(ticket, pos.stop_loss, None, reason="stop_loss")
                elif pos.take_profit is not None and mid <= pos.take_profit:
                    self._settle(ticket, pos.take_profit, None, reason="take_profit")

    def _settle(
        self, ticket: str, exit_price: float, lots: float | None, reason: str
    ) -> Fill:
        pos = self._positions[ticket]
        inst = self.get_instrument(pos.symbol)
        close_lots = pos.lots if lots is None else inst.round_lots(min(lots, pos.lots))
        if close_lots <= 0:
            raise BrokerError(f"{pos.symbol}: partial close size rounds to zero")

        pnl = inst.pnl_in_account(pos.entry_price, exit_price, close_lots, pos.is_long)
        self.balance += pnl
        self.closed_trades.append(
            {
                "ticket": ticket,
                "symbol": pos.symbol,
                "side": pos.side.value,
                "lots": close_lots,
                "entry_price": pos.entry_price,
                "exit_price": exit_price,
                "pnl": pnl,
                "reason": reason,
                "opened_at": pos.opened_at,
                "closed_at": utcnow(),
            }
        )

        remaining = round(pos.lots - close_lots, 9)
        if remaining <= 0:
            del self._positions[ticket]
        else:
            pos.lots = remaining

        return Fill(
            ticket=ticket,
            client_id="",
            symbol=pos.symbol,
            side=pos.side.opposite,
            lots=close_lots,
            price=exit_price,
            filled_at=self._stamp(),
        )


def make_candles(
    start: datetime, count: int, timeframe_minutes: int, start_price: float, step: float = 0.0
) -> list[Candle]:
    """Build a simple synthetic series. Handy for tests and demos."""
    out = []
    price = start_price
    for i in range(count):
        ts = start + timedelta(minutes=timeframe_minutes * i)
        close = price + step
        out.append(
            Candle(
                timestamp=ts.replace(tzinfo=timezone.utc) if ts.tzinfo is None else ts,
                open=price,
                high=max(price, close) + abs(step) * 0.5,
                low=min(price, close) - abs(step) * 0.5,
                close=close,
                volume=1000.0,
            )
        )
        price = close
    return out
