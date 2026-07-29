"""The backtester must run on simulated time, not today's date.

This bug was silent and expensive. PaperBroker stamped every position with
utcnow(), so in a replay of 2025 data every simulated trade claimed to have
been opened today. Nothing crashed. But every rule that reasons about time --
how long a trade has been held, how many trades happened today, whether this
is still the same session -- was comparing a 2025 candle against 2026 and
quietly evaluating to nothing. A hold-time limit tested as a perfect no-op
across seven different settings, which read like "holding time doesn't matter"
rather than "the feature never ran".
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from tradebot.backtest.engine import BacktestBroker
from tradebot.brokers.base import BracketOrder, Candle, OrderSide
from tradebot.instruments import Instrument

INST = Instrument(
    symbol="US30", contract_size=1.0, tick_size=1.0, min_lot=0.01, max_lot=100.0,
    lot_step=0.01, base_currency="US30", quote_currency="USD", digits=1,
    correlation_group="INDICES",
)


def _broker() -> BacktestBroker:
    b = BacktestBroker(starting_balance=10_000.0, spread_pct=0.0, fee_pct=0.0)
    b.connect()
    b.register_instrument(INST)
    return b


def test_position_is_stamped_with_candle_time_not_wall_clock() -> None:
    b = _broker()
    bar_time = datetime(2025, 3, 4, 14, 30, tzinfo=timezone.utc)
    b.advance("US30", Candle(
        timestamp=bar_time, open=40_000, high=40_050, low=39_950,
        close=40_000, volume=1.0,
    ))
    b.submit_bracket(BracketOrder(
        symbol="US30", side=OrderSide.BUY, lots=0.1,
        stop_loss=39_900.0, take_profit=40_200.0,
    ))
    opened = b.get_positions()[0].opened_at
    assert opened == bar_time, (
        f"position stamped {opened}, expected the candle's own time {bar_time}"
    )


def test_hold_time_is_positive_and_grows_with_replay() -> None:
    b = _broker()
    start = datetime(2025, 3, 4, 14, 30, tzinfo=timezone.utc)
    b.advance("US30", Candle(timestamp=start, open=40_000, high=40_050,
                             low=39_950, close=40_000, volume=1.0))
    b.submit_bracket(BracketOrder(
        symbol="US30", side=OrderSide.BUY, lots=0.1,
        stop_loss=39_900.0, take_profit=40_500.0,
    ))
    pos = b.get_positions()[0]

    later = start + timedelta(minutes=45)
    b.advance("US30", Candle(timestamp=later, open=40_000, high=40_020,
                             low=39_980, close=40_010, volume=1.0))
    held = (b.now - pos.opened_at).total_seconds() / 60
    assert held == 45, f"held for {held} minutes, expected 45"


def test_paper_broker_still_uses_wall_clock() -> None:
    """The fix must not leak into live or paper trading, where now is now."""
    from tradebot.brokers.paper import PaperBroker

    p = PaperBroker(starting_balance=10_000.0)
    p.connect()
    p.register_instrument(INST)
    p.set_price("US30", 40_000.0)
    p.submit_bracket(BracketOrder(
        symbol="US30", side=OrderSide.BUY, lots=0.1,
        stop_loss=39_900.0, take_profit=40_200.0,
    ))
    opened = p.get_positions()[0].opened_at
    assert (datetime.now(timezone.utc) - opened).total_seconds() < 60
