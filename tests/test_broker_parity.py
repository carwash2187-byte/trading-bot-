"""Broker abstraction parity.

The promise is that strategy code cannot tell which broker it is talking to.
These tests drive the paper simulator and *mocked* MT5 and TradeLocker
adapters through the identical sequence and assert identical behaviour.

No network calls and no credentials — the mocks stand in for both.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from tradebot.brokers.base import (
    BracketOrder,
    Broker,
    BrokerError,
    LiveModeRefused,
    OrderSide,
    TradingMode,
)
from tradebot.brokers.paper import PaperBroker
from tradebot.brokers.tradelocker import TradeLockerBroker
from tradebot.instruments import get_instrument


# ---------------------------------------------------------------------------
# Live-mode gate
# ---------------------------------------------------------------------------

def test_default_mode_is_paper():
    assert PaperBroker().mode is TradingMode.PAPER


def test_live_mode_refused_without_the_env_opt_in(monkeypatch):
    monkeypatch.delenv("TRADEBOT_ALLOW_LIVE", raising=False)
    with pytest.raises(LiveModeRefused):
        TradeLockerBroker(mode=TradingMode.LIVE)


def test_live_mode_refused_when_env_var_has_the_wrong_value(monkeypatch):
    monkeypatch.setenv("TRADEBOT_ALLOW_LIVE", "true")   # not the magic value
    with pytest.raises(LiveModeRefused):
        TradeLockerBroker(mode=TradingMode.LIVE)


def test_live_mode_allowed_only_with_the_explicit_opt_in(monkeypatch):
    monkeypatch.setenv("TRADEBOT_ALLOW_LIVE", "yes")
    broker = TradeLockerBroker(mode=TradingMode.LIVE)
    assert broker.is_live
    assert broker.base_url.startswith("https://live.")


def test_demo_mode_points_at_the_demo_host(monkeypatch):
    monkeypatch.setenv("TRADEBOT_ALLOW_LIVE", "yes")     # even so, demo stays demo
    broker = TradeLockerBroker(mode=TradingMode.DEMO)
    assert not broker.is_live
    assert broker.base_url.startswith("https://demo.")


def test_paper_broker_cannot_be_forced_live(monkeypatch):
    monkeypatch.setenv("TRADEBOT_ALLOW_LIVE", "yes")
    with pytest.raises(BrokerError):
        PaperBroker(mode=TradingMode.LIVE)


# ---------------------------------------------------------------------------
# Bracket orders
# ---------------------------------------------------------------------------

def test_bracket_requires_a_stop_loss():
    with pytest.raises(ValueError):
        BracketOrder(symbol="EURUSD", side=OrderSide.BUY, lots=0.1, stop_loss=0)


def test_bracket_rejects_a_stop_on_the_wrong_side():
    with pytest.raises(ValueError):
        BracketOrder(
            symbol="EURUSD", side=OrderSide.BUY, lots=0.1,
            stop_loss=1.2000, order_type=__import__(
                "tradebot.brokers.base", fromlist=["OrderType"]
            ).OrderType.LIMIT, limit_price=1.1000,
        )


def test_paper_broker_holds_the_stop_server_side():
    broker = PaperBroker(starting_balance=10_000.0, spread=0.0)
    broker.connect()
    broker.set_price("XAUUSD", 2000.0)
    fill = broker.submit_bracket(
        BracketOrder("XAUUSD", OrderSide.BUY, 0.1, stop_loss=1990.0, take_profit=2020.0)
    )
    assert broker.get_position(fill.ticket) is not None

    # Price gaps through the stop with no bot involvement at all.
    broker.set_price("XAUUSD", 1985.0)
    assert broker.get_position(fill.ticket) is None
    assert broker.balance < 10_000.0


def test_take_profit_also_fires_unattended():
    broker = PaperBroker(starting_balance=10_000.0, spread=0.0)
    broker.connect()
    broker.set_price("XAUUSD", 2000.0)
    broker.submit_bracket(
        BracketOrder("XAUUSD", OrderSide.BUY, 0.5, stop_loss=1990.0, take_profit=2010.0)
    )
    broker.set_price("XAUUSD", 2015.0)
    assert broker.get_positions() == []
    # 0.5 lots * 100 oz * $10 = $500.
    assert broker.balance == pytest.approx(10_500.0)


# ---------------------------------------------------------------------------
# Mocked adapters
# ---------------------------------------------------------------------------

def _tradelocker_responses() -> dict:
    """Canned TradeLocker REST payloads keyed by 'METHOD path-prefix'."""
    return {
        "POST /auth/jwt/token": {"accessToken": "fake-token"},
        "GET /auth/jwt/all-accounts": {"accounts": [{"id": "42", "accNum": "1"}]},
        # Shaped like the real API, verified against a live AquaFunded account.
        # The list carries no contract size at all, and the routes are three
        # distinct numbers: the instrument id, an INFO route for quotes and a
        # TRADE route for orders. An earlier version of this fixture invented a
        # "contractSize" field on the list, so the adapter's fallback to the
        # forex default of 100,000 was never exercised -- gold was being sized
        # a thousand times too large and every test still passed.
        "GET /trade/accounts/42/instruments": {
            "d": {"instruments": [{
                "name": "XAUUSD",
                "tradableInstrumentId": 7,
                "description": "Gold vs US Dollar - Spot",
                "routes": [{"id": 900, "type": "TRADE"},
                           {"id": 800, "type": "INFO"}],
            }]}
        },
        "GET /trade/instruments/7": {
            "d": {
                "lotSize": 100,
                "tickSize": [{"leftRangeLimit": None, "tickSize": 0.01}],
                "minLot": 0.01, "maxLot": 50.0, "lotStep": 0.01,
                "baseCurrency": None, "quotingCurrency": "USD",
            }
        },
        # The real column order, read from a live account. It is deliberately
        # not the obvious one -- side before quantity, and the stop/take fields
        # are order IDS rather than prices.
        "GET /trade/config": {
            "d": {"positionsConfig": {"columns": [
                {"id": "id"}, {"id": "tradableInstrumentId"}, {"id": "routeId"},
                {"id": "side"}, {"id": "qty"}, {"id": "avgPrice"},
                {"id": "stopLossId"}, {"id": "takeProfitId"}, {"id": "openDate"},
                {"id": "unrealizedPl"}, {"id": "strategyId"},
            ]}}
        },
        "GET /trade/quotes": {"d": {"bp": 1999.5, "ap": 2000.5}},
        "POST /trade/accounts/42/orders": {"d": {"orderId": "TL-123"}},
        "GET /trade/accounts/42/state": {"d": {"accountDetailsData": [10_000.0, 10_050.0, 0.0, 10_000.0]}},
        "GET /trade/accounts/42/positions": {"d": {"positions": []}},
    }


def _fake_request(responses):
    def _request(self, method, path, body=None, auth=True):
        for key, payload in responses.items():
            verb, prefix = key.split(" ", 1)
            if method == verb and path.startswith(prefix):
                return payload
        raise BrokerError(f"unmocked call {method} {path}")
    return _request


@pytest.fixture
def mock_tradelocker():
    responses = _tradelocker_responses()
    with patch.object(TradeLockerBroker, "_request", _fake_request(responses)):
        broker = TradeLockerBroker(
            username="u", password="p", server="s", account_id="42",
            mode=TradingMode.DEMO,
        )
        broker.connect()
        yield broker


def test_tradelocker_reads_contract_size_from_the_broker(mock_tradelocker):
    """Trusting the broker's own numbers is what prevents a stale multiplier."""
    inst = mock_tradelocker.get_instrument("XAUUSD")
    assert inst.contract_size == 100
    assert inst.units(1.0) == 100


def test_tradelocker_sends_lots_not_units(mock_tradelocker):
    """The order payload must carry lots. Sending units would be 100x wrong."""
    captured = {}

    def capture(self, method, path, body=None, auth=True):
        if method == "POST" and path.endswith("/orders"):
            captured.update(body or {})
            return {"d": {"orderId": "TL-9"}}
        return _fake_request(_tradelocker_responses())(self, method, path, body, auth)

    with patch.object(TradeLockerBroker, "_request", capture):
        mock_tradelocker.submit_bracket(
            BracketOrder("XAUUSD", OrderSide.BUY, 0.25, stop_loss=1990.0)
        )
    assert captured["qty"] == pytest.approx(0.25)
    assert captured["stopLoss"] == pytest.approx(1990.0)


def test_tradelocker_attaches_the_stop_to_the_entry(mock_tradelocker):
    captured = {}

    def capture(self, method, path, body=None, auth=True):
        if method == "POST" and path.endswith("/orders"):
            captured.update(body or {})
            return {"d": {"orderId": "TL-9"}}
        return _fake_request(_tradelocker_responses())(self, method, path, body, auth)

    with patch.object(TradeLockerBroker, "_request", capture):
        mock_tradelocker.submit_bracket(
            BracketOrder("XAUUSD", OrderSide.BUY, 0.1, stop_loss=1990.0, take_profit=2020.0)
        )
    assert "stopLoss" in captured and "takeProfit" in captured


def test_tradelocker_account_snapshot(mock_tradelocker):
    acct = mock_tradelocker.get_account()
    assert acct.balance == pytest.approx(10_000.0)
    assert acct.equity == pytest.approx(10_050.0)


def test_tradelocker_rejects_a_size_below_min_lot(mock_tradelocker):
    with pytest.raises(BrokerError):
        mock_tradelocker.submit_bracket(
            BracketOrder("XAUUSD", OrderSide.BUY, 0.001, stop_loss=1990.0)
        )


# ---------------------------------------------------------------------------
# Parity: identical behaviour across implementations
# ---------------------------------------------------------------------------

ABSTRACT_METHODS = [
    "connect", "disconnect", "get_instrument", "get_price", "get_candles",
    "submit_bracket", "close_position", "modify_protection", "get_positions",
    "get_account",
]


@pytest.mark.parametrize("cls", [PaperBroker, TradeLockerBroker])
def test_every_adapter_implements_the_full_interface(cls):
    for name in ABSTRACT_METHODS:
        assert callable(getattr(cls, name, None)), f"{cls.__name__} missing {name}"
    assert not getattr(cls, "__abstractmethods__", set())


def test_mt5_adapter_implements_the_interface_without_importing_mt5():
    """The MT5 package only exists on Windows; importing our module must not need it."""
    from tradebot.brokers.mt5 import MT5Broker

    for name in ABSTRACT_METHODS:
        assert callable(getattr(MT5Broker, name, None))
    assert not MT5Broker.__abstractmethods__


def test_mt5_reports_a_clear_error_when_the_package_is_absent():
    from tradebot.brokers.mt5 import MT5Broker

    broker = MT5Broker(mode=TradingMode.DEMO)
    with patch.dict("sys.modules", {"MetaTrader5": None}):
        with pytest.raises(BrokerError, match="only installs on Windows"):
            broker.connect()


def test_mt5_refuses_a_live_account_while_in_demo_mode():
    """Wrong-terminal protection: demo mode must not trade a real account."""
    from tradebot.brokers.mt5 import MT5Broker

    fake = MagicMock()
    fake.initialize.return_value = True
    fake.login.return_value = True
    fake.ACCOUNT_TRADE_MODE_DEMO = 0
    fake.account_info.return_value = MagicMock(trade_mode=2, login=555)

    broker = MT5Broker(login=555, mode=TradingMode.DEMO)
    with patch.dict("sys.modules", {"MetaTrader5": fake}):
        with pytest.raises(BrokerError, match="not a demo account"):
            broker.connect()


def test_paper_and_tradelocker_agree_on_pnl_for_the_same_trade(mock_tradelocker):
    """Same instrument, same prices, same maths — regardless of adapter."""
    tl_inst = mock_tradelocker.get_instrument("XAUUSD")
    paper_inst = get_instrument("XAUUSD")

    args = (2000.0, 2010.0, 0.3, True)
    assert tl_inst.pnl_in_account(*args) == pytest.approx(paper_inst.pnl_in_account(*args))
    assert tl_inst.pnl_in_account(*args) == pytest.approx(300.0)


# ---------------------------------------------------------------------------
# Regressions from the first real connection. Every one of these passed
# against a mock and failed against the actual broker.
# ---------------------------------------------------------------------------

def test_a_missing_lot_size_refuses_rather_than_guessing():
    """The bug that would have mis-sized every gold trade by 1000x.

    Contract size lives only in the details endpoint, and the old code
    defaulted to the forex 100,000 when it was absent. Gold's real lot is 100
    ounces, so positions were described a thousand times too large. A loud
    failure is worth far more than a silently wrong size on a funded account.
    """
    from tradebot.brokers.base import BrokerError
    from tradebot.brokers.tradelocker import TradeLockerBroker

    row = {"name": "XAUUSD"}
    with pytest.raises(BrokerError, match="lot size"):
        TradeLockerBroker._to_instrument(row, {})

    with pytest.raises(BrokerError, match="lot size"):
        TradeLockerBroker._to_instrument(row, {"lotSize": 0})


def test_gold_is_a_hundred_ounces_not_a_hundred_thousand():
    from tradebot.brokers.tradelocker import TradeLockerBroker

    instrument = TradeLockerBroker._to_instrument(
        {"name": "XAUUSD"},
        {"lotSize": 100, "tickSize": [{"tickSize": 0.01}],
         "minLot": 0.01, "lotStep": 0.01, "quotingCurrency": "USD"},
    )
    assert instrument.contract_size == 100.0
    assert instrument.digits == 2          # derived from the tick, not guessed


def test_quotes_and_orders_use_different_routes(mock_tradelocker):
    """TradeLocker answers a wrong route with an empty quote, not an error.

    That is indistinguishable from a symbol which does not exist, so using the
    instrument id for both looked like "gold is not tradable here".
    """
    broker = mock_tradelocker
    assert broker._instrument_id("XAUUSD") == 7
    assert broker._route("XAUUSD", "INFO") == 800
    assert broker._route("XAUUSD", "TRADE") == 900


def test_minute_resolutions_are_lower_case():
    """Upper-case M means MONTHS. "15M" asks for fifteen-month bars."""
    from tradebot.brokers.tradelocker import _RESOLUTIONS

    assert _RESOLUTIONS["15m"] == "15m"
    assert _RESOLUTIONS["5m"] == "5m"
    assert _RESOLUTIONS["1h"] == "1H"      # hours stay upper-case
    assert _RESOLUTIONS["1d"] == "1D"


def test_a_second_position_on_the_same_symbol_is_refused():
    """The bug that would have emptied the account.

    A strategy is shown only the positions attributed to it. When that
    attribution fails -- a broker that returns no order comment, a renamed
    strategy, a restart -- it believes it is flat while holding a position and
    opens another every cycle. RSI can sit oversold for hours, so that is a
    dozen entries stacked at several times the intended size.

    The guard lives in the risk layer, not the strategy, so it holds no matter
    which strategy asks or what it thinks it owns.
    """
    from datetime import datetime, timezone

    from tradebot.brokers.base import Position
    from tradebot.risk.limits import RiskLimits, RiskManager

    risk = RiskManager(RiskLimits())
    held = Position(
        ticket="1", symbol="XAUUSD", side=OrderSide.BUY, lots=0.07,
        entry_price=4000.0, stop_loss=3990.0, take_profit=None,
        opened_at=datetime.now(timezone.utc),
        comment="",                       # attribution lost, as it would be
    )

    decision = risk.check_entry(
        equity=10_000.0, symbol="XAUUSD", correlation_group="METALS",
        open_positions=[held],
    )
    assert not decision.allowed
    assert "already holding" in decision.detail

    # A different symbol is still fine -- this is not a blanket freeze.
    assert risk.check_entry(
        equity=10_000.0, symbol="EURUSD", correlation_group="EUR",
        open_positions=[held],
    ).allowed


def test_position_fields_are_read_by_name_not_by_guessed_order(mock_tradelocker):
    """TradeLocker sends positions as bare arrays in a non-obvious order.

    Element 3 is the side, not the quantity; element 8 is the open date, not
    the stop price. Read positionally from a guess, a position parses into a
    different symbol with side and size swapped -- and the strategy, asked
    "do I hold this?", answers no.
    """
    columns = mock_tradelocker._position_columns()
    assert columns["side"] == 3
    assert columns["qty"] == 4
    assert columns["openDate"] == 8
    assert columns["unrealizedPl"] == 9


def test_the_owning_strategy_survives_the_round_trip(mock_tradelocker):
    """Without this the stack cannot tell whose position is whose."""
    captured = {}

    def capture(self, method, path, body=None, auth=True):
        if method == "POST" and path.endswith("/orders"):
            captured.update(body or {})
            return {"d": {"orderId": "TL-9"}}
        return _fake_request(_tradelocker_responses())(self, method, path, body, auth)

    with patch.object(TradeLockerBroker, "_request", capture):
        mock_tradelocker.submit_bracket(BracketOrder(
            symbol="XAUUSD", side=OrderSide.BUY, lots=0.07,
            stop_loss=1990.0, comment="gold_scalper",
        ))
    assert captured.get("strategyId") == "gold_scalper"


def test_the_bot_halts_before_the_limit_that_ends_the_account():
    """A 6% drawdown does not compute as 6%.

    Binary floating point makes a drawdown of exactly the limit come out as
    0.059999999999999984, which is not >= 0.06 -- so a check written against
    the limit itself keeps trading at the precise moment the prop firm is
    closing the account. Stopping short of the line sidesteps that, and leaves
    room for slippage and stale equity reads besides.
    """
    from tradebot.risk.limits import RiskLimits, RiskManager

    limits = RiskLimits(daily_loss_limit=0.03, max_drawdown_limit=0.06)
    start = 2635.39

    def allowed_at(fraction: float) -> bool:
        risk = RiskManager(limits)
        risk.state.peak_equity = start
        risk.state.day_start_equity = start
        return risk.check_entry(
            equity=start * fraction, symbol="XAUUSD",
            correlation_group="METALS", open_positions=[],
        ).allowed

    assert allowed_at(0.99)          # 1% down, fine
    assert not allowed_at(0.946)     # 5.4%, the stop
    assert not allowed_at(0.94)      # 6%, where the account would have died


def test_the_safety_margin_is_configurable_and_off_by_default_is_not_an_option():
    from tradebot.risk.limits import RiskLimits

    assert RiskLimits().safety_margin < 1.0
    # Explicitly settable, so a live account with no external rule can use the
    # full allowance if that is genuinely wanted.
    assert RiskLimits(safety_margin=1.0).safety_margin == 1.0
