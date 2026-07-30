"""A history request the server will not serve must not look like an empty market.

TradeLocker answers an over-wide time range with an empty bar list rather than a
short one. Measured on UK100: asking for 5,000 bars of 15m returns 5,000, while
asking for 20,000 returns ZERO -- because 20,000 bars of 15m asks for a 626-day
window and the endpoint declines it.

An empty list is indistinguishable from an instrument with no history, so a live
strategy pointed at a thinner market would silently never trade and look exactly
like a strategy with no signal. That is the same failure shape as every other
silent-rule bug in this project, except this one would happen with real money on
the line.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from tradebot.brokers.base import BrokerError
from tradebot.brokers.tradelocker import TradeLockerBroker


class _FakeBroker(TradeLockerBroker):
    """A broker whose server only serves windows under ``max_days``."""

    def __init__(self, max_days: float, bars_available: int = 500) -> None:
        self.max_days = max_days
        self.bars_available = bars_available
        self.calls: list[float] = []
        self._connected = True

    def _instrument_id(self, symbol: str) -> int:      # noqa: D102
        return 1

    def _route(self, symbol: str, kind: str) -> int:   # noqa: D102
        return 1

    def _request(self, method: str, path: str):        # noqa: D102
        import urllib.parse

        query = urllib.parse.parse_qs(path.split("?", 1)[1])
        start = int(query["from"][0]) / 1000
        end = int(query["to"][0]) / 1000
        days = (end - start) / 86400
        self.calls.append(days)
        if days > self.max_days:
            return {"d": {"barDetails": []}}      # the server's silent refusal
        base = datetime(2026, 1, 1, tzinfo=timezone.utc)
        return {"d": {"barDetails": [
            {
                "t": int((base + timedelta(minutes=15 * i)).timestamp() * 1000),
                "o": 100.0, "h": 101.0, "l": 99.0, "c": 100.5, "v": 1.0,
            }
            for i in range(self.bars_available)
        ]}}


def test_wide_window_narrows_instead_of_returning_nothing() -> None:
    broker = _FakeBroker(max_days=90)
    bars = broker.get_candles("UK100", "15m", 20_000)
    assert bars, "an over-wide window must be narrowed, not surrendered to"
    assert len(broker.calls) > 1, "should have retried with a smaller window"
    assert broker.calls[1] < broker.calls[0], "the window should shrink"


def test_short_history_returns_what_exists() -> None:
    broker = _FakeBroker(max_days=10_000, bars_available=300)
    bars = broker.get_candles("UK100", "15m", 20_000)
    assert len(bars) == 300, "should hand back everything the server had"


def test_genuinely_empty_market_raises_rather_than_lying() -> None:
    """No history at any window width is a fault, not a flat market."""
    broker = _FakeBroker(max_days=-1)   # refuses every window
    with pytest.raises(BrokerError, match="no history"):
        broker.get_candles("UK100", "15m", 500)
