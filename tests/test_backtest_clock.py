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


def test_hold_cap_fires_outside_the_trading_session() -> None:
    """A hold cap must not sit behind an entry gate.

    The cap was first placed after MambaBreakout's session check, which returns
    early outside New York hours. So it only ever fired during the session, and
    a trade opened at 04:00 ran for 1425 minutes under a "180 minute cap". The
    resulting hold-time table measured something other than its own label and
    made a losing setting look like the best one found all session.
    """
    from datetime import time as _time

    from tradebot.strategy.mamba import MambaBreakout

    strat = MambaBreakout(max_hold_minutes=180)
    # 03:00 UTC is outside every session this strategy trades.
    off_session = datetime(2025, 10, 2, 3, 0, tzinfo=timezone.utc)
    assert strat._active_session(off_session) is None, (
        "test needs an off-session time to be meaningful"
    )

    opened = off_session - timedelta(minutes=600)
    ctx = _context_with_position(off_session, opened)
    actions = strat.evaluate(ctx)
    assert actions, "a 600-minute-old trade must be closed even off-session"
    assert actions[0].__class__.__name__ == "Exit"


def _context_with_position(now: datetime, opened_at: datetime):
    """A context holding one open position and enough bars to be evaluated."""
    from tradebot.brokers.base import OrderSide, Position
    from tradebot.strategy.base import StrategyContext

    candles = [
        Candle(
            timestamp=now - timedelta(minutes=15 * (100 - i)),
            open=46_000, high=46_050, low=45_950, close=46_000, volume=1.0,
        )
        for i in range(100)
    ]
    pos = Position(
        ticket="P000001", symbol="US30", side=OrderSide.SELL, lots=0.06,
        entry_price=46_000.0, stop_loss=46_100.0, take_profit=45_200.0,
        opened_at=opened_at, comment="mamba_breakout",
    )
    from tradebot.brokers.base import AccountSnapshot
    from tradebot.risk.limits import RiskLimits, RiskManager

    return StrategyContext(
        symbol="US30", instrument=INST, candles=candles,
        bid=46_000.0, ask=46_001.0,
        account=AccountSnapshot(
            balance=150.0, equity=150.0, currency="USD",
            margin_used=0.0, margin_free=150.0, taken_at=now,
        ),
        open_positions=[pos], news=None,
        risk=RiskManager(RiskLimits()), now=now,
    )


def test_backtest_rolls_the_risk_day_over() -> None:
    """The backtest must age the risk day, or everything daily is a no-op.

    The engine never called update_equity, so RiskState.current_day stayed empty
    for an entire run. Two things silently did nothing as a result: the
    daily-loss breaker never armed, and the per-strategy daily trade counter
    never reset -- turning "max 3 trades a day" into "max 3 trades ever". A
    3.5-month run took 3 trades and looked like a strategy with no signal.
    """
    from tradebot.backtest import run_backtest
    from tradebot.strategy.base import Enter, Strategy
    from tradebot.brokers.base import OrderSide

    class OnePerDay(Strategy):
        """Wants one trade every bar; a working cap should hold it to one a day."""

        name = "one_per_day"
        timeframe = "15m"
        lookback = 5

        def evaluate(self, context):
            if context.has_position:
                return []
            if context.risk.trades_today(self.name) >= 1:
                return []
            # Both sides must be reachable within a bar or two, or the first
            # trade never closes and has_position blocks the rest of the run --
            # which looks exactly like a broken daily counter.
            return [Enter(
                side=OrderSide.BUY,
                stop_loss=context.bid - 80.0,
                take_profit=context.bid + 80.0,
                comment=self.name,
            )]

    start = datetime(2025, 3, 3, tzinfo=timezone.utc)
    candles = []
    price = 40_000.0
    for i in range(300):
        price += 20 if (i // 7) % 2 == 0 else -18
        candles.append(Candle(
            timestamp=start + timedelta(minutes=15 * i),
            open=price, high=price + 60, low=price - 60,
            close=price, volume=1.0,
        ))

    result = run_backtest(
        OnePerDay(), candles, symbol="US30", timeframe="15m", instrument=INST,
        starting_balance=100_000.0, risk_per_trade=0.01,
        spread_pct=0.0, fee_pct=0.0,
    )
    days = len({c.timestamp.date() for c in candles})
    assert days > 2, "test needs to span several days"
    # One a day, not one for the whole run.
    assert len(result.trades) >= days - 1, (
        f"{len(result.trades)} trades across {days} days -- the daily counter "
        "is not resetting"
    )
