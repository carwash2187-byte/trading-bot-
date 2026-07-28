"""TradeLocker adapter.

TradeLocker is what most prop firms run, so this adapter is the one that
matters for a funded account. It speaks the REST API over HTTPS using only the
standard library, so there is no SDK to pin or to break.

Two TradeLocker specifics worth knowing:

* Environments are fully separate. The demo host is a different base URL from
  the live host, so paper and live cannot be confused by a wrong account id
  alone — but the live-mode gate in :class:`Broker` still applies on top.
* Quantities are sent in *lots*. All conversion to units happens in
  :mod:`tradebot.instruments`; nothing here multiplies by contract size, which
  is what keeps the 100,000x class of bug out of this file.

Network calls are intentionally thin and every one raises :class:`BrokerError`
on failure so the cycle's error isolation can catch it and retry next pass.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
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

DEMO_HOST = "https://demo.tradelocker.com/backend-api"
LIVE_HOST = "https://live.tradelocker.com/backend-api"

# TradeLocker sits behind Cloudflare, which rejects the default urllib
# identifier outright with a 403 "browser signature banned" before the request
# ever reaches the API. Identifying as an ordinary browser is what the platform
# expects from a client; without it every call fails on a login error that has
# nothing to do with the credentials.
BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": "https://demo.tradelocker.com",
    "Referer": "https://demo.tradelocker.com/",
}

# TradeLocker resolution codes for the timeframes this package uses.
_RESOLUTIONS = {
    "1m": "1M", "5m": "5M", "15m": "15M", "30m": "30M",
    "1h": "1H", "4h": "4H", "1d": "1D",
}


class TradeLockerBroker(Broker):
    """REST adapter for TradeLocker demo and live environments.

    Args:
        username / password / server: TradeLocker account credentials.
        account_id: Which account under that login to trade.
        mode: PAPER/DEMO hit the demo host; LIVE requires the env opt-in.
        timeout: Per-request timeout in seconds.
    """

    def __init__(
        self,
        username: str = "",
        password: str = "",
        server: str = "",
        account_id: str = "",
        mode: TradingMode = TradingMode.DEMO,
        timeout: float = 15.0,
    ) -> None:
        super().__init__(mode=mode)
        self.username = username
        self.password = password
        self.server = server
        self.account_id = account_id
        self.timeout = timeout
        # The host itself is chosen by mode, so a demo-mode bot physically
        # cannot reach the live endpoint even with live credentials.
        self.base_url = LIVE_HOST if self.is_live else DEMO_HOST
        self._token: str | None = None
        self._acc_num: str | None = None
        self._instrument_cache: dict[str, Instrument] = {}
        self._route_cache: dict[str, int] = {}

    # -- transport -------------------------------------------------------

    def _request(
        self, method: str, path: str, body: dict | None = None, auth: bool = True
    ) -> dict:
        url = f"{self.base_url}{path}"
        data = json.dumps(body).encode("utf-8") if body is not None else None
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        headers.update(BROWSER_HEADERS)
        if self.base_url.startswith(LIVE_HOST):
            headers["Origin"] = "https://live.tradelocker.com"
            headers["Referer"] = "https://live.tradelocker.com/"
        if auth:
            if not self._token:
                raise BrokerError("not authenticated; call connect() first")
            headers["Authorization"] = f"Bearer {self._token}"
            if self._acc_num:
                headers["accNum"] = str(self._acc_num)

        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as err:
            detail = err.read().decode("utf-8", "replace")[:400]
            # A Cloudflare block reads as an auth failure but has nothing to do
            # with the credentials, and chasing the wrong cause wastes a lot of
            # time on a first connection.
            if err.code == 403 and "1010" in detail:
                raise BrokerError(
                    "blocked by Cloudflare before reaching TradeLocker, not a "
                    "login problem. The client identifier was rejected."
                ) from err
            raise BrokerError(f"TradeLocker {method} {path} -> {err.code}: {detail}") from err
        except (urllib.error.URLError, OSError, json.JSONDecodeError) as err:
            raise BrokerError(f"TradeLocker {method} {path} failed: {err}") from err

    # -- lifecycle -------------------------------------------------------

    def connect(self) -> None:
        if self._connected:
            return
        payload = self._request(
            "POST",
            "/auth/jwt/token",
            {"email": self.username, "password": self.password, "server": self.server},
            auth=False,
        )
        self._token = payload.get("accessToken")
        if not self._token:
            raise BrokerError("TradeLocker login returned no access token")

        accounts = self._request("GET", "/auth/jwt/all-accounts").get("accounts", [])
        if not accounts:
            raise BrokerError("TradeLocker login succeeded but exposed no accounts")

        chosen = None
        for acc in accounts:
            if not self.account_id or str(acc.get("id")) == str(self.account_id):
                chosen = acc
                break
        if chosen is None:
            raise BrokerError(f"account {self.account_id!r} not found on this login")

        self.account_id = str(chosen["id"])
        self._acc_num = str(chosen.get("accNum", ""))
        self._connected = True

    def disconnect(self) -> None:
        self._token = None
        self._acc_num = None
        self._connected = False

    # -- market data -----------------------------------------------------

    def _instrument_id(self, symbol: str) -> int:
        """The tradableInstrumentId, which is not a route id -- see _route()."""
        if symbol.upper() in self._route_cache:
            return self._route_cache[symbol.upper()][0]
        payload = self._request("GET", f"/trade/accounts/{self.account_id}/instruments")
        for row in payload.get("d", {}).get("instruments", []):
            name = str(row.get("name", "")).upper()
            routes = {str(r.get("type", "")).upper(): int(r.get("id"))
                      for r in row.get("routes", []) if r.get("id") is not None}
            self._route_cache[name] = (
                int(row.get("tradableInstrumentId")),
                routes.get("INFO"),
                routes.get("TRADE"),
            )
            self._instrument_cache[name] = self._to_instrument(row)
        try:
            return self._route_cache[symbol.upper()][0]
        except KeyError:
            raise BrokerError(f"{symbol} is not tradable on this account") from None

    def _route(self, symbol: str, kind: str) -> int:
        """The route id for quotes ("INFO") or orders ("TRADE").

        These are three different numbers and TradeLocker will not tell you
        when the wrong one is used -- it returns an empty quote rather than an
        error, which reads exactly like a symbol that does not exist. Gold on
        this account is instrument 1714, INFO route 791554, TRADE route 795894.
        """
        self._instrument_id(symbol)              # ensure the cache is warm
        iid, info, trade = self._route_cache[symbol.upper()]
        route = info if kind == "INFO" else trade
        # Falling back to the instrument id keeps older accounts working, where
        # the routes list is sometimes absent entirely.
        return route if route is not None else iid

    @staticmethod
    def _to_instrument(row: dict) -> Instrument:
        """Build an Instrument from TradeLocker's own contract details.

        Preferring the broker's numbers over a local constant is what stops a
        stale contract size from silently misstating every trade.
        """
        symbol = str(row.get("name", "")).upper()
        return Instrument(
            symbol=symbol,
            contract_size=float(row.get("contractSize", 100_000) or 100_000),
            tick_size=float(row.get("tickSize", 0.00001) or 0.00001),
            min_lot=float(row.get("minLotSize", 0.01) or 0.01),
            max_lot=float(row.get("maxLotSize", 100.0) or 100.0),
            lot_step=float(row.get("lotSizeStep", 0.01) or 0.01),
            base_currency=str(row.get("baseCurrency", "")),
            quote_currency=str(row.get("quoteCurrency", "USD")),
            digits=int(row.get("digits", 5) or 5),
            description=str(row.get("description", "")),
        )

    def get_instrument(self, symbol: str) -> Instrument:
        key = symbol.upper()
        if key not in self._instrument_cache:
            try:
                self._instrument_id(key)      # populates both caches
            except BrokerError:
                return get_instrument(key)    # fall back to the local catalogue
        return self._instrument_cache.get(key) or get_instrument(key)

    def get_price(self, symbol: str) -> tuple[float, float]:
        iid = self._instrument_id(symbol)
        payload = self._request(
            "GET",
            f"/trade/quotes?routeId={self._route(symbol, 'INFO')}"
            f"&tradableInstrumentId={iid}",
        )
        quote = payload.get("d", {})
        try:
            return (float(quote["bp"]), float(quote["ap"]))
        except (KeyError, TypeError, ValueError):
            raise BrokerError(f"no usable quote for {symbol}: {quote}") from None

    def get_candles(
        self, symbol: str, timeframe: str, count: int, end: datetime | None = None
    ) -> list[Candle]:
        iid = self._instrument_id(symbol)
        resolution = _RESOLUTIONS.get(timeframe.lower())
        if resolution is None:
            raise BrokerError(f"unsupported timeframe {timeframe!r}")
        end = end or utcnow()
        params = urllib.parse.urlencode(
            {
                "routeId": self._route(symbol, "INFO"),
                "tradableInstrumentId": iid,
                "resolution": resolution,
                "to": int(end.timestamp() * 1000),
                "countBack": count,
            }
        )
        payload = self._request("GET", f"/trade/history?{params}")
        out = []
        for bar in payload.get("d", {}).get("barDetails", []):
            out.append(
                Candle(
                    timestamp=datetime.fromtimestamp(int(bar["t"]) / 1000, tz=timezone.utc),
                    open=float(bar["o"]),
                    high=float(bar["h"]),
                    low=float(bar["l"]),
                    close=float(bar["c"]),
                    volume=float(bar.get("v", 0) or 0),
                )
            )
        return out

    # -- trading ---------------------------------------------------------

    def submit_bracket(self, order: BracketOrder) -> Fill:
        """Send the entry with stop and target attached in the same payload.

        TradeLocker holds both server-side once accepted, so the position stays
        protected if this process dies.
        """
        iid = self._instrument_id(order.symbol)
        inst = self.get_instrument(order.symbol)
        lots = inst.round_lots(order.lots)
        if lots <= 0:
            raise BrokerError(f"{order.symbol}: size rounds below min lot {inst.min_lot}")

        body = {
            "price": order.limit_price or 0,
            "qty": lots,                      # lots, never units
            "routeId": self._route(order.symbol, "TRADE"),
            "side": "buy" if order.side.is_long else "sell",
            "tradableInstrumentId": iid,
            "type": order.order_type.value,
            "validity": "IOC" if order.order_type is OrderType.MARKET else "GTC",
            "stopLoss": inst.round_price(order.stop_loss),
            "stopLossType": "absolute",
        }
        if order.take_profit is not None:
            body["takeProfit"] = inst.round_price(order.take_profit)
            body["takeProfitType"] = "absolute"

        payload = self._request("POST", f"/trade/accounts/{self.account_id}/orders", body)
        order_id = str(payload.get("d", {}).get("orderId", ""))
        if not order_id:
            raise BrokerError(f"order rejected by TradeLocker: {payload}")

        bid, ask = self.get_price(order.symbol)
        return Fill(
            ticket=order_id,
            client_id=order.client_id,
            symbol=order.symbol.upper(),
            side=order.side,
            lots=lots,
            price=ask if order.side.is_long else bid,
            filled_at=utcnow(),
            stop_loss=order.stop_loss,
            take_profit=order.take_profit,
        )

    def close_position(self, ticket: str, lots: float | None = None) -> Fill:
        body = {"qty": lots} if lots is not None else {}
        self._request("DELETE", f"/trade/positions/{ticket}", body or None)
        pos = self.get_position(ticket)
        symbol = pos.symbol if pos else ""
        bid, ask = self.get_price(symbol) if symbol else (0.0, 0.0)
        side = pos.side.opposite if pos else OrderSide.SELL
        return Fill(
            ticket=ticket,
            client_id="",
            symbol=symbol,
            side=side,
            lots=lots or (pos.lots if pos else 0.0),
            price=bid if side is OrderSide.SELL else ask,
            filled_at=utcnow(),
        )

    def modify_protection(
        self, ticket: str, stop_loss: float | None = None, take_profit: float | None = None
    ) -> None:
        body: dict = {}
        if stop_loss is not None:
            body["stopLoss"] = stop_loss
        if take_profit is not None:
            body["takeProfit"] = take_profit
        if not body:
            return
        self._request("PATCH", f"/trade/positions/{ticket}", body)

    def get_positions(self) -> list[Position]:
        payload = self._request("GET", f"/trade/accounts/{self.account_id}/positions")
        out = []
        for row in payload.get("d", {}).get("positions", []):
            try:
                out.append(
                    Position(
                        ticket=str(row[0]),
                        symbol=str(row[1]).upper(),
                        side=OrderSide.BUY if str(row[4]).lower() == "buy" else OrderSide.SELL,
                        lots=float(row[3]),
                        entry_price=float(row[5]),
                        stop_loss=float(row[8]) if row[8] else None,
                        take_profit=float(row[9]) if row[9] else None,
                        opened_at=datetime.fromtimestamp(
                            int(row[2]) / 1000, tz=timezone.utc
                        ),
                        unrealized_pnl=float(row[10]) if len(row) > 10 and row[10] else 0.0,
                    )
                )
            except (IndexError, TypeError, ValueError):
                continue   # one odd row must not hide the rest of the book
        return out

    def get_account(self) -> AccountSnapshot:
        payload = self._request("GET", f"/trade/accounts/{self.account_id}/state")
        state = payload.get("d", {}).get("accountDetailsData", [])
        try:
            return AccountSnapshot(
                balance=float(state[0]),
                equity=float(state[1]),
                currency="USD",
                margin_used=float(state[2]) if len(state) > 2 else 0.0,
                margin_free=float(state[3]) if len(state) > 3 else 0.0,
            )
        except (IndexError, TypeError, ValueError):
            raise BrokerError(f"could not read account state: {payload}") from None
