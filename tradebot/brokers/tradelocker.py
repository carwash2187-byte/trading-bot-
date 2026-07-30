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
import math
import urllib.error
import logging
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

from ..data.ohlc import timeframe_minutes
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

log = logging.getLogger("tradebot.tradelocker")

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

# TradeLocker resolution codes. The case is not cosmetic: minutes are
# lower-case and months are upper-case, so "15M" asks for fifteen-MONTH bars
# and the API rejects the request outright. That was worth an hour -- the
# symptom is an empty candle list, which is indistinguishable from a market
# that simply has no history yet.
#
# The full set the API accepts: 1m, 5m, 15m, 30m, 1H, 4H, 1D, 1W, 1M.
# Note there is no 2h; strategies on that timeframe must build it from 1H.
_RESOLUTIONS = {
    "1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m",
    "1h": "1H", "4h": "4H", "1d": "1D", "1w": "1W",
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
        # Bars, held until the bar they belong to closes. See get_candles.
        self._candle_cache: dict[tuple, tuple] = {}
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
        self._route_cache: dict[str, tuple] = {}
        self._rows: dict[str, dict] = {}
        self._columns: dict[str, int] | None = None
        self._acct_columns: dict[str, int] | None = None

    # -- transport -------------------------------------------------------

    def _request(
        self, method: str, path: str, body: dict | None = None, auth: bool = True
    ) -> dict:
        """One API call, with self-repair for the failures that repair safely.

        GETs are retried on network blips and server-side 5xx errors: reading
        a price twice is harmless, and a cloud runner's network hiccuping for
        a second should not abort a whole trading cycle.

        Anything that changes state -- placing an order, closing a position,
        moving a stop -- is deliberately NEVER retried here. A POST that times
        out may still have landed, and re-sending it is how one intended
        position becomes two. The safe recovery for that case lives elsewhere:
        the risk layer refuses a second position on a held symbol, so if the
        lost order did land, the next cycle sees it and stands down.
        """
        attempts = 3 if method == "GET" else 1
        delay = 1.0
        for attempt in range(attempts):
            try:
                return self._request_once(method, path, body, auth)
            except BrokerError as err:
                text = str(err)
                transient = ("failed:" in text          # URLError / timeout
                             or "-> 5" in text)         # 500/502/503/504
                if attempt < attempts - 1 and transient:
                    import time
                    time.sleep(delay)
                    delay *= 3
                    continue
                raise
        raise BrokerError("unreachable")                 # for the type checker

    def _request_once(
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
            self._rows[name] = row
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
    def _to_instrument(row: dict, details: dict) -> Instrument:
        """Build an Instrument from TradeLocker's own contract details.

        The contract size lives in the per-instrument *details* endpoint under
        ``lotSize``, and is absent from the instrument list entirely. Defaulting
        when it is missing is what this method used to do, and the default was
        the forex 100,000 -- so gold, whose real lot is 100 ounces, was being
        described a thousand times too large. Every position size computed from
        it would have been wrong by that factor.

        So there is no default any more. A missing contract size raises, because
        a loud failure at startup is worth far more than a silently mis-sized
        trade on a funded account.
        """
        symbol = str(row.get("name", "")).upper()

        lot_size = details.get("lotSize")
        if lot_size in (None, 0):
            raise BrokerError(
                f"{symbol}: TradeLocker did not report a lot size. Refusing to "
                f"guess -- a wrong contract size mis-sizes every trade."
            )

        # tickSize arrives as a list of ranges, finest first.
        ticks = details.get("tickSize") or []
        tick = float(ticks[0]["tickSize"]) if ticks else 0.01

        return Instrument(
            symbol=symbol,
            contract_size=float(lot_size),
            tick_size=tick,
            min_lot=float(details.get("minLot") or 0.01),
            max_lot=float(details.get("maxLot") or 100.0),
            lot_step=float(details.get("lotStep") or 0.01),
            base_currency=str(details.get("baseCurrency") or symbol[:3]),
            quote_currency=str(details.get("quotingCurrency") or "USD"),
            # Digits follow from the tick: 0.01 is two decimals, 0.00001 five.
            digits=max(0, round(-math.log10(tick))) if tick > 0 else 2,
            description=str(row.get("description", "")),
        )

    def get_instrument(self, symbol: str) -> Instrument:
        key = symbol.upper()
        if key in self._instrument_cache:
            return self._instrument_cache[key]

        iid = self._instrument_id(key)        # populates self._rows
        details = self._request(
            "GET",
            f"/trade/instruments/{iid}?routeId={self._route(key, 'INFO')}&locale=en",
        )
        instrument = self._to_instrument(self._rows[key], details.get("d", details))
        self._instrument_cache[key] = instrument
        return instrument

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
        """Bars, cached until the next one is actually due.

        THIS IS WHAT MAKES A ONE-SECOND LOOP POSSIBLE.

        Every cycle asked the broker for candles again, and on a five-second loop
        across four markets that is roughly 14 requests a second -- over a million
        a day at one provider. Brokers throttle or ban for that, and a banned bot
        does not trade at all, which is worse than a slow one.

        But a 5-minute candle only changes every 5 minutes. Re-downloading it 300
        times in between buys nothing. What genuinely moves second to second is
        the PRICE, and `get_price` is a separate, much cheaper call that is not
        cached at all.

        So the bars are held until the bar they belong to closes. That cuts the
        per-symbol cost of a cycle from three requests to one, and the saving
        grows the faster the loop runs -- at one second it is a ~99% reduction on
        the candle traffic. His entry is intrabar anyway ("I'm going to get in
        right on that wick"), and intrabar means the live price, not a new bar.
        """
        # Created on first use rather than in __init__, because a subclass that
        # does not call super().__init__() would otherwise raise AttributeError
        # here -- which is exactly what happened to the history tests, and would
        # equally happen to any custom broker someone wrote later.
        cache = getattr(self, "_candle_cache", None)
        if cache is None:
            cache = {}
            self._candle_cache = cache

        # Captured BEFORE `end` is defaulted to now, a few lines below. Testing
        # `end is None` again at the bottom is always False by then, so the cache
        # read worked while the cache WRITE never ran -- it stored nothing, and
        # looked completely implemented while doing so. Exactly the shape of the
        # silent rules this project keeps turning up, in a different file.
        cacheable = end is None

        if cacheable:
            minutes = max(1, timeframe_minutes(timeframe))
            now = utcnow()
            # Which bar are we inside? The cache is valid for the whole of it.
            bar_index = int(now.timestamp()) // (minutes * 60)
            key = (symbol.upper(), timeframe.lower(), count)
            hit = cache.get(key)
            if hit is not None and hit[0] == bar_index:
                return hit[1]

        iid = self._instrument_id(symbol)
        resolution = _RESOLUTIONS.get(timeframe.lower())
        if resolution is None:
            raise BrokerError(f"unsupported timeframe {timeframe!r}")
        end = end or utcnow()
        # The API wants a time range, not a bar count -- "countBack" is
        # rejected outright. Ask for a generous span and trim, since the
        # market is shut at weekends and overnight, so N bars covers far more
        # than N periods of wall-clock time.
        minutes = timeframe_minutes(timeframe)
        span = timedelta(minutes=minutes * count * 3 + 1440)

        # Asking for a window the server will not serve comes back EMPTY, not
        # short. Measured on UK100: 5,000 bars of 15m returns 5,000, while 20,000
        # returns zero -- because 20,000 bars asks for a 626-day range and the
        # endpoint simply declines it. An empty list is indistinguishable from a
        # market with no history, so a strategy pointed at a thinner instrument
        # would silently never trade and look like it had no signal.
        #
        # So halve the span and retry rather than accept the silence. Each retry
        # still returns the most recent bars, which is what a strategy needs.
        out: list[Candle] = []
        for _ in range(6):
            params = urllib.parse.urlencode(
                {
                    "routeId": self._route(symbol, "INFO"),
                    "tradableInstrumentId": iid,
                    "resolution": resolution,
                    "from": int((end - span).timestamp() * 1000),
                    "to": int(end.timestamp() * 1000),
                }
            )
            payload = self._request("GET", f"/trade/history?{params}")
            bars = payload.get("d", {}).get("barDetails", [])
            if bars:
                for bar in bars:
                    out.append(
                        Candle(
                            timestamp=datetime.fromtimestamp(
                                int(bar["t"]) / 1000, tz=timezone.utc
                            ),
                            open=float(bar["o"]),
                            high=float(bar["h"]),
                            low=float(bar["l"]),
                            close=float(bar["c"]),
                            volume=float(bar.get("v", 0) or 0),
                        )
                    )
                break
            span = span / 2
            if span < timedelta(minutes=minutes * 20):
                break

        if not out:
            raise BrokerError(
                f"no history returned for {symbol} {timeframe} after narrowing "
                f"the window; the instrument may have none"
            )
        if len(out) < count:
            log.warning(
                "%s %s: asked for %d bars, server had %d",
                symbol, timeframe, count, len(out),
            )
        bars = out[-count:]
        if cacheable:
            minutes = max(1, timeframe_minutes(timeframe))
            bar_index = int(utcnow().timestamp()) // (minutes * 60)
            cache = getattr(self, "_candle_cache", None)
            if cache is None:
                cache = {}
                self._candle_cache = cache
            cache[(symbol.upper(), timeframe.lower(), count)] = (bar_index, bars)
            # Never let it grow without bound across a long session.
            if len(cache) > 64:
                cache.clear()
        return bars

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
        # Which strategy owns this. TradeLocker returns it on the position as
        # `strategyId`, and it is the only field that survives the round trip --
        # the order "comment" other brokers carry does not exist here. Without
        # it the stack cannot tell whose position is whose, every strategy
        # believes it is flat, and each opens another position every cycle.
        if order.comment:
            body["strategyId"] = order.comment[:32]
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
        # Read the position BEFORE deleting it. The obvious order -- delete,
        # then look at what closed -- looks up a position that no longer
        # exists, and every field degrades to a default: symbol "", exit price
        # 0.0. The journal then books the close at zero, a five-figure fake
        # loss on gold, and the portfolio manager benches the strategy for a
        # catastrophe that never happened. Wrong-looking numbers would at
        # least get investigated; these flow straight into the stats.
        pos = self.get_position(ticket)
        if pos is None:
            raise BrokerError(
                f"position {ticket} not found; nothing to close. If it was "
                f"just closed by its bracket, this is a stale ticket, not an "
                f"error in the account."
            )
        bid, ask = self.get_price(pos.symbol)

        body = {"qty": lots} if lots is not None else {}
        self._request("DELETE", f"/trade/positions/{ticket}", body or None)

        side = pos.side.opposite
        return Fill(
            ticket=ticket,
            client_id="",
            symbol=pos.symbol,
            side=side,
            lots=lots or pos.lots,
            # The price the market showed the instant before the close went
            # in -- the closest honest estimate this API offers, since the
            # DELETE returns no fill details.
            price=bid if side is OrderSide.SELL else ask,
            filled_at=utcnow(),
        )

    def modify_protection(
        self, ticket: str, stop_loss: float | None = None, take_profit: float | None = None
    ) -> None:
        # The type fields mirror what submit_bracket sends. Absolute prices are
        # what every strategy in this codebase computes; omitting the type and
        # letting the server assume one is the kind of default that works until
        # the day it doesn't. Live-unverified: the running strategy uses fixed
        # brackets and never moves a stop, so this path has no live traffic yet.
        body: dict = {}
        if stop_loss is not None:
            body["stopLoss"] = stop_loss
            body["stopLossType"] = "absolute"
        if take_profit is not None:
            body["takeProfit"] = take_profit
            body["takeProfitType"] = "absolute"
        if not body:
            return
        self._request("PATCH", f"/trade/positions/{ticket}", body)

    def _position_columns(self) -> dict[str, int]:
        """Where each field sits in a position row, asked of the broker.

        Positions come back as bare arrays with no field names, and the real
        order is nothing like the obvious guess -- element 3 is the side, not
        the quantity, and element 8 is the open date, not the stop price. Read
        positionally from a guess, a position parses into a different symbol,
        with side and size swapped and a timestamp as its stop.

        That is worse than a crash. The strategy asks "do I already hold this?"
        and a mangled symbol answers no, so it would open a second position on
        top of the first.

        So the layout is read from /trade/config once per connection and cached.
        Asking is also robust to TradeLocker reordering the columns later.
        """
        if self._columns is None:
            config = self._request("GET", "/trade/config")
            block = config.get("d", config).get("positionsConfig", {})
            self._columns = {
                str(column.get("id")): index
                for index, column in enumerate(block.get("columns", []))
            }
        return self._columns

    def get_positions(self) -> list[Position]:
        columns = self._position_columns()
        payload = self._request("GET", f"/trade/accounts/{self.account_id}/positions")

        def field(row, name, default=None):
            index = columns.get(name)
            if index is None or index >= len(row):
                return default
            return row[index]

        out = []
        for row in payload.get("d", {}).get("positions", []):
            try:
                instrument_id = field(row, "tradableInstrumentId")
                out.append(
                    Position(
                        ticket=str(field(row, "id")),
                        symbol=self._symbol_for(instrument_id),
                        side=(OrderSide.BUY
                              if str(field(row, "side", "")).lower() == "buy"
                              else OrderSide.SELL),
                        lots=float(field(row, "qty", 0)),
                        entry_price=float(field(row, "avgPrice", 0)),
                        # stopLossId and takeProfitId are order identifiers, not
                        # prices -- the levels are not in this payload at all.
                        # Reporting the id as a price would be a plausible-
                        # looking number in the right field, which is the most
                        # dangerous kind of wrong.
                        stop_loss=None,
                        take_profit=None,
                        opened_at=datetime.fromtimestamp(
                            int(field(row, "openDate", 0)) / 1000, tz=timezone.utc
                        ),
                        unrealized_pnl=float(field(row, "unrealizedPl", 0) or 0),
                        # The stack matches positions to strategies on this.
                        comment=str(field(row, "strategyId", "") or ""),
                    )
                )
            except (IndexError, TypeError, ValueError):
                continue   # one odd row must not hide the rest of the book
        return out

    def _symbol_for(self, instrument_id) -> str:
        """Turn a tradableInstrumentId back into the name the bot uses."""
        if instrument_id is None:
            return ""
        for name, (iid, _info, _trade) in self._route_cache.items():
            if str(iid) == str(instrument_id):
                return name
        # Warm the cache and try once more; a position may be open on an
        # instrument this session has not looked up yet.
        try:
            self._instrument_id("XAUUSD")
        except BrokerError:
            return ""
        for name, (iid, _info, _trade) in self._route_cache.items():
            if str(iid) == str(instrument_id):
                return name
        return ""

    def _account_columns(self) -> dict[str, int]:
        """Field positions for the account-state array, asked of the broker.

        Same disease as positions, same cure. The guessed order had [1] as
        equity when it is really projectedBalance, and [3] as free margin when
        it is really blockedBalance -- which on this account is a constant 0,
        so the margin-aware position cap would have read "nothing affordable"
        and silently stopped the live bot from ever trading again.
        """
        if self._acct_columns is None:
            config = self._request("GET", "/trade/config")
            block = config.get("d", config).get("accountDetailsConfig", {})
            self._acct_columns = {
                str(column.get("id")): index
                for index, column in enumerate(block.get("columns", []))
            }
        return self._acct_columns

    def get_account(self) -> AccountSnapshot:
        columns = self._account_columns()
        payload = self._request("GET", f"/trade/accounts/{self.account_id}/state")
        state = payload.get("d", {}).get("accountDetailsData", [])

        def field(name, default=0.0):
            index = columns.get(name)
            if index is None or index >= len(state):
                return default
            try:
                return float(state[index])
            except (TypeError, ValueError):
                return default

        balance = field("balance")
        if balance <= 0 and not state:
            raise BrokerError(f"could not read account state: {payload}")
        # There is no plain "equity" column; the truthful equivalent is the
        # settled balance plus the open positions' net floating P&L.
        equity = balance + field("openNetPnL")
        return AccountSnapshot(
            balance=balance,
            equity=equity,
            currency="USD",
            margin_used=field("initialMarginReq"),
            # availableFunds is what the venue will actually let new margin
            # draw on -- the honest input for the position cap.
            margin_free=field("availableFunds"),
        )
