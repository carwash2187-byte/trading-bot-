"""MetaTrader5 adapter.

Wraps the official ``MetaTrader5`` Python package, which talks to a running
terminal on the same Windows machine. The import is deferred to
:meth:`connect` so the rest of this package — and the whole test suite — works
on macOS and Linux where that package cannot be installed.

MT5 reports volume in lots and prices in points. As with TradeLocker, no
contract-size arithmetic happens here; it all lives in
:mod:`tradebot.instruments`.
"""

from __future__ import annotations

from datetime import datetime, timezone

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

_TIMEFRAMES = {
    "1m": "TIMEFRAME_M1", "5m": "TIMEFRAME_M5", "15m": "TIMEFRAME_M15",
    "30m": "TIMEFRAME_M30", "1h": "TIMEFRAME_H1", "4h": "TIMEFRAME_H4",
    "1d": "TIMEFRAME_D1",
}


class MT5Broker(Broker):
    """MetaTrader5 terminal adapter.

    Args:
        login / password / server: Terminal account credentials.
        path: Optional explicit path to ``terminal64.exe``.
        mode: PAPER/DEMO expect a demo terminal; LIVE needs the env opt-in.
        magic: Magic number stamped on this bot's orders so they can be told
            apart from anything placed by hand in the terminal.
    """

    def __init__(
        self,
        login: int = 0,
        password: str = "",
        server: str = "",
        path: str | None = None,
        mode: TradingMode = TradingMode.DEMO,
        magic: int = 660_066,
        deviation: int = 20,
    ) -> None:
        super().__init__(mode=mode)
        self.login = login
        self.password = password
        self.server = server
        self.path = path
        self.magic = magic
        self.deviation = deviation
        self._mt5 = None

    # -- lifecycle -------------------------------------------------------

    def connect(self) -> None:
        if self._connected:
            return
        try:
            import MetaTrader5 as mt5  # noqa: N813 - vendor's own casing
        except ImportError as err:
            raise BrokerError(
                "MetaTrader5 package not available. It only installs on Windows "
                "with a running MT5 terminal. Use PaperBroker or "
                "TradeLockerBroker elsewhere."
            ) from err

        self._mt5 = mt5
        kwargs = {"path": self.path} if self.path else {}
        if not mt5.initialize(**kwargs):
            raise BrokerError(f"MT5 initialize failed: {mt5.last_error()}")

        if self.login:
            if not mt5.login(self.login, password=self.password, server=self.server):
                mt5.shutdown()
                raise BrokerError(f"MT5 login failed: {mt5.last_error()}")

        info = mt5.account_info()
        if info is None:
            mt5.shutdown()
            raise BrokerError("MT5 connected but returned no account info")

        # Belt and braces: refuse to run against a real account unless the
        # operator asked for LIVE explicitly. The base class already gated the
        # flag; this catches a demo-mode bot pointed at a live terminal.
        is_demo = getattr(info, "trade_mode", 0) == getattr(mt5, "ACCOUNT_TRADE_MODE_DEMO", 0)
        if not is_demo and not self.is_live:
            mt5.shutdown()
            raise BrokerError(
                f"MT5 account {info.login} is not a demo account but the broker "
                f"is in {self.mode.value} mode. Refusing to connect."
            )

        self._connected = True

    def disconnect(self) -> None:
        if self._mt5 is not None:
            try:
                self._mt5.shutdown()
            except Exception:  # noqa: BLE001 - shutdown must never raise
                pass
        self._connected = False

    def _require(self):
        if self._mt5 is None or not self._connected:
            raise BrokerError("MT5 not connected")
        return self._mt5

    # -- market data -----------------------------------------------------

    def get_instrument(self, symbol: str) -> Instrument:
        mt5 = self._require()
        info = mt5.symbol_info(symbol)
        if info is None:
            return get_instrument(symbol)
        return Instrument(
            symbol=symbol.upper(),
            contract_size=float(info.trade_contract_size),
            tick_size=float(info.trade_tick_size or info.point),
            min_lot=float(info.volume_min),
            max_lot=float(info.volume_max),
            lot_step=float(info.volume_step),
            base_currency=str(info.currency_base),
            quote_currency=str(info.currency_profit),
            digits=int(info.digits),
            description=str(info.description),
        )

    def get_price(self, symbol: str) -> tuple[float, float]:
        mt5 = self._require()
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            raise BrokerError(f"no tick for {symbol}: {mt5.last_error()}")
        return (float(tick.bid), float(tick.ask))

    def get_candles(
        self, symbol: str, timeframe: str, count: int, end: datetime | None = None
    ) -> list[Candle]:
        mt5 = self._require()
        tf_name = _TIMEFRAMES.get(timeframe.lower())
        if tf_name is None:
            raise BrokerError(f"unsupported timeframe {timeframe!r}")
        tf = getattr(mt5, tf_name)

        rates = (
            mt5.copy_rates_from(symbol, tf, end, count)
            if end
            else mt5.copy_rates_from_pos(symbol, tf, 0, count)
        )
        if rates is None:
            raise BrokerError(f"no candles for {symbol}: {mt5.last_error()}")
        return [
            Candle(
                timestamp=datetime.fromtimestamp(int(r["time"]), tz=timezone.utc),
                open=float(r["open"]),
                high=float(r["high"]),
                low=float(r["low"]),
                close=float(r["close"]),
                volume=float(r["tick_volume"]),
            )
            for r in rates
        ]

    # -- trading ---------------------------------------------------------

    def submit_bracket(self, order: BracketOrder) -> Fill:
        mt5 = self._require()
        inst = self.get_instrument(order.symbol)
        lots = inst.round_lots(order.lots)
        if lots <= 0:
            raise BrokerError(f"{order.symbol}: size rounds below min lot {inst.min_lot}")

        bid, ask = self.get_price(order.symbol)
        price = ask if order.side.is_long else bid

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": order.symbol,
            "volume": lots,                    # lots, never units
            "type": mt5.ORDER_TYPE_BUY if order.side.is_long else mt5.ORDER_TYPE_SELL,
            "price": price,
            "sl": inst.round_price(order.stop_loss),
            "deviation": self.deviation,
            "magic": self.magic,
            "comment": order.comment[:31],     # MT5 truncates past 31 chars
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        if order.take_profit is not None:
            request["tp"] = inst.round_price(order.take_profit)

        result = mt5.order_send(request)
        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            code = getattr(result, "retcode", "no result")
            comment = getattr(result, "comment", mt5.last_error())
            raise BrokerError(f"MT5 order rejected ({code}): {comment}")

        return Fill(
            ticket=str(result.order),
            client_id=order.client_id,
            symbol=order.symbol.upper(),
            side=order.side,
            lots=float(result.volume),
            price=float(result.price),
            filled_at=utcnow(),
            stop_loss=order.stop_loss,
            take_profit=order.take_profit,
        )

    def close_position(self, ticket: str, lots: float | None = None) -> Fill:
        mt5 = self._require()
        positions = mt5.positions_get(ticket=int(ticket))
        if not positions:
            raise BrokerError(f"position {ticket} not found")
        pos = positions[0]

        close_lots = float(lots) if lots is not None else float(pos.volume)
        is_long = pos.type == mt5.POSITION_TYPE_BUY
        bid, ask = self.get_price(pos.symbol)

        result = mt5.order_send(
            {
                "action": mt5.TRADE_ACTION_DEAL,
                "position": int(ticket),
                "symbol": pos.symbol,
                "volume": close_lots,
                "type": mt5.ORDER_TYPE_SELL if is_long else mt5.ORDER_TYPE_BUY,
                "price": bid if is_long else ask,
                "deviation": self.deviation,
                "magic": self.magic,
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
        )
        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            raise BrokerError(f"MT5 close rejected: {getattr(result, 'comment', '?')}")

        return Fill(
            ticket=str(ticket),
            client_id="",
            symbol=pos.symbol.upper(),
            side=OrderSide.SELL if is_long else OrderSide.BUY,
            lots=float(result.volume),
            price=float(result.price),
            filled_at=utcnow(),
        )

    def modify_protection(
        self, ticket: str, stop_loss: float | None = None, take_profit: float | None = None
    ) -> None:
        mt5 = self._require()
        positions = mt5.positions_get(ticket=int(ticket))
        if not positions:
            raise BrokerError(f"position {ticket} not found")
        pos = positions[0]
        result = mt5.order_send(
            {
                "action": mt5.TRADE_ACTION_SLTP,
                "position": int(ticket),
                "symbol": pos.symbol,
                "sl": stop_loss if stop_loss is not None else pos.sl,
                "tp": take_profit if take_profit is not None else pos.tp,
                "magic": self.magic,
            }
        )
        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            raise BrokerError(f"MT5 SLTP change rejected: {getattr(result, 'comment', '?')}")

    def get_positions(self) -> list[Position]:
        mt5 = self._require()
        rows = mt5.positions_get() or []
        return [
            Position(
                ticket=str(p.ticket),
                symbol=str(p.symbol).upper(),
                side=OrderSide.BUY if p.type == mt5.POSITION_TYPE_BUY else OrderSide.SELL,
                lots=float(p.volume),
                entry_price=float(p.price_open),
                stop_loss=float(p.sl) or None,
                take_profit=float(p.tp) or None,
                opened_at=datetime.fromtimestamp(int(p.time), tz=timezone.utc),
                unrealized_pnl=float(p.profit),
                comment=str(p.comment),
            )
            for p in rows
            if not self.magic or p.magic == self.magic
        ]

    def get_account(self) -> AccountSnapshot:
        mt5 = self._require()
        info = mt5.account_info()
        if info is None:
            raise BrokerError("MT5 returned no account info")
        return AccountSnapshot(
            balance=float(info.balance),
            equity=float(info.equity),
            currency=str(info.currency),
            margin_used=float(info.margin),
            margin_free=float(info.margin_free),
        )
