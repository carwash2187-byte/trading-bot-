"""Portfolio management, scoring, and the concrete trend strategies.

The behaviour worth protecting here is not "does it trade" but "does it stop
trading the right thing". A manager that benches a good strategy, or keeps a
dead one running, is worse than no manager at all.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from tradebot.brokers.base import Candle, OrderSide, Position
from tradebot.data.indicators import highest, kama, lowest, williams_r
from tradebot.portfolio.manager import ACTIVE, BENCHED, PortfolioManager
from tradebot.portfolio.scorecard import COLD, HEALTHY, UNPROVEN, score_strategies
from tradebot.risk.journal import JournalEntry, TradeJournal
from tradebot.strategy.base import Enter, Exit, Strategy, StrategyContext
from tradebot.strategy.stack import StrategyStack
from tradebot.strategy.trend import BreakoutRider, KamaTrend

NOW = datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def candles(closes: list[float], spread: float = 1.0) -> list[Candle]:
    """Build bars from a close series, with highs/lows bracketing each close."""
    out = []
    for i, close in enumerate(closes):
        out.append(
            Candle(
                timestamp=NOW - timedelta(hours=2 * (len(closes) - i)),
                open=close,
                high=close + spread,
                low=close - spread,
                close=close,
                volume=100.0,
            )
        )
    return out


def write_trades(journal: TradeJournal, strategy: str, pnls: list[float],
                 days_ago: float = 1.0) -> None:
    closed = NOW - timedelta(days=days_ago)
    for i, pnl in enumerate(pnls):
        journal.record(
            JournalEntry(
                ticket=f"{strategy}-{i}",
                symbol="XAUUSD",
                side="buy",
                lots=0.1,
                entry_price=2000.0,
                exit_price=2000.0 + pnl,
                opened_at=(closed - timedelta(hours=4)).isoformat(),
                closed_at=closed.isoformat(),
                realized_pnl=pnl,
                strategy=strategy,
            )
        )


# ---------------------------------------------------------------------------
# Indicators
# ---------------------------------------------------------------------------

def test_highest_and_lowest_use_inclusive_window():
    values = [1.0, 5.0, 3.0, 2.0]
    assert highest(values, 2) == [None, 5.0, 5.0, 3.0]
    assert lowest(values, 2) == [None, 1.0, 3.0, 2.0]


def test_kama_tracks_a_clean_trend_closely():
    """In a straight line KAMA speeds up, so it should sit near price."""
    rising = [float(i) for i in range(1, 61)]
    line = kama(rising, period=10)
    assert line[-1] is not None
    assert abs(line[-1] - rising[-1]) < 3.0


def test_kama_lags_far_behind_in_chop():
    """In noise it slows down, which is the whole point of it being adaptive."""
    choppy = [100.0 + (5.0 if i % 2 else -5.0) for i in range(60)]
    line = kama(choppy, period=10)
    seed = line[9]
    assert seed is not None and line[-1] is not None
    # Price whipsaws 95<->105 fifty times; an adaptive average should drift
    # barely at all from where it started rather than chase every swing.
    assert abs(line[-1] - seed) < 2.0


def test_williams_r_marks_range_extremes():
    bars = candles([10.0, 12.0, 14.0, 16.0, 20.0], spread=0.0)
    wpr = williams_r(bars, period=5)
    assert wpr[-1] == pytest.approx(0.0)      # closing at the very top

    bars = candles([20.0, 18.0, 16.0, 12.0, 10.0], spread=0.0)
    wpr = williams_r(bars, period=5)
    assert wpr[-1] == pytest.approx(-100.0)   # closing at the very bottom


def test_williams_r_handles_a_flat_range_without_dividing_by_zero():
    wpr = williams_r(candles([50.0] * 6, spread=0.0), period=5)
    assert wpr[-1] == -50.0


# ---------------------------------------------------------------------------
# Scorecard
# ---------------------------------------------------------------------------

def test_losing_strategy_is_marked_cold(tmp_path):
    journal = TradeJournal(tmp_path / "j.jsonl")
    write_trades(journal, "loser", [-10.0] * 8 + [5.0, 5.0])
    scores = score_strategies(journal, min_trades=5, now=NOW)
    assert scores["loser"].verdict == COLD
    assert scores["loser"].profit_factor < 1.0


def test_winning_strategy_is_marked_healthy(tmp_path):
    journal = TradeJournal(tmp_path / "j.jsonl")
    write_trades(journal, "winner", [30.0] * 6 + [-10.0] * 4)
    scores = score_strategies(journal, min_trades=5, now=NOW)
    assert scores["winner"].verdict == HEALTHY
    assert scores["winner"].profit_factor == pytest.approx(4.5)


def test_small_sample_is_unproven_not_healthy(tmp_path):
    """Three lucky trades must not be mistaken for a working edge."""
    journal = TradeJournal(tmp_path / "j.jsonl")
    write_trades(journal, "lucky", [50.0, 50.0, 50.0])
    scores = score_strategies(journal, min_trades=10, now=NOW)
    assert scores["lucky"].verdict == UNPROVEN


def test_scoring_window_ignores_old_trades(tmp_path):
    """A strategy that worked last year but not this month must score on now."""
    journal = TradeJournal(tmp_path / "j.jsonl")
    write_trades(journal, "faded", [100.0] * 20, days_ago=200)
    write_trades(journal, "faded", [-10.0] * 12, days_ago=2)
    scores = score_strategies(journal, window_days=14, min_trades=5, now=NOW)
    assert scores["faded"].trades == 12
    assert scores["faded"].verdict == COLD


def test_naive_timestamps_are_not_silently_dropped(tmp_path):
    """Older rows lack a timezone; comparing them must not raise or discard."""
    journal = TradeJournal(tmp_path / "j.jsonl")
    journal.record(
        JournalEntry(
            ticket="t1", symbol="XAUUSD", side="buy", lots=0.1,
            entry_price=1.0, exit_price=2.0,
            opened_at="2026-06-30T00:00:00",
            closed_at="2026-06-30T12:00:00",     # no tzinfo on purpose
            realized_pnl=5.0, strategy="legacy",
        )
    )
    scores = score_strategies(journal, window_days=14, min_trades=1, now=NOW)
    assert scores["legacy"].trades == 1


# ---------------------------------------------------------------------------
# The manager
# ---------------------------------------------------------------------------

class Dummy(Strategy):
    timeframe = "2h"
    lookback = 50

    def __init__(self, name: str) -> None:
        self.name = name

    def evaluate(self, context):
        return []


def make_manager(tmp_path, names=("a", "b"), **kwargs):
    journal = TradeJournal(tmp_path / "j.jsonl")
    manager = PortfolioManager(
        roster=[Dummy(n) for n in names],
        journal=journal,
        state_path=tmp_path / "portfolio.json",
        min_trades=kwargs.pop("min_trades", 5),
        **kwargs,
    )
    return manager, journal


def test_everything_starts_active(tmp_path):
    manager, _ = make_manager(tmp_path)
    assert {s.name for s in manager.active_strategies()} == {"a", "b"}


def test_cold_strategy_is_benched_and_the_rest_keep_running(tmp_path):
    manager, journal = make_manager(tmp_path)
    write_trades(journal, "a", [-10.0] * 10)
    write_trades(journal, "b", [20.0] * 8 + [-5.0] * 2)

    report = manager.review(now=NOW)
    assert report.benched == ["a"]
    assert [s.name for s in manager.active_strategies()] == ["b"]


def test_unproven_strategy_is_left_alone(tmp_path):
    """Too few trades is not evidence of failure, so it keeps its place."""
    manager, journal = make_manager(tmp_path, min_trades=10)
    write_trades(journal, "a", [-10.0, -10.0])
    report = manager.review(now=NOW)
    assert report.benched == []
    assert "a" in report.active


def test_benching_survives_a_restart(tmp_path):
    manager, journal = make_manager(tmp_path)
    write_trades(journal, "a", [-10.0] * 10)
    manager.review(now=NOW)

    # A scheduled bot exits between runs; the decision must be on disk.
    revived, _ = make_manager(tmp_path)
    assert revived.slots["a"].status == BENCHED
    assert [s.name for s in revived.active_strategies()] == ["b"]


def test_benched_strategy_does_not_return_before_probation(tmp_path):
    manager, journal = make_manager(tmp_path, probation_days=14)
    write_trades(journal, "a", [-10.0] * 10)
    manager.review(now=NOW)

    # It now looks healthy, but not enough time has passed to trust that.
    write_trades(journal, "a", [50.0] * 10, days_ago=0.5)
    report = manager.review(now=NOW + timedelta(days=3))
    assert report.restored == []
    assert manager.slots["a"].status == BENCHED


def test_benched_strategy_returns_once_it_serves_time_and_recovers(tmp_path):
    manager, journal = make_manager(tmp_path, probation_days=14)
    write_trades(journal, "a", [-10.0] * 10)
    manager.review(now=NOW)

    later = NOW + timedelta(days=20)
    write_trades(journal, "a", [50.0] * 10, days_ago=-19)   # after the benching
    report = manager.review(now=later)
    assert report.restored == ["a"]
    assert manager.slots["a"].status == ACTIVE


def test_a_strategy_added_later_starts_active(tmp_path):
    manager, journal = make_manager(tmp_path, names=("a",))
    manager.review(now=NOW)
    grown = PortfolioManager(
        roster=[Dummy("a"), Dummy("new")],
        journal=journal,
        state_path=tmp_path / "portfolio.json",
    )
    assert grown.slots["new"].status == ACTIVE


# ---------------------------------------------------------------------------
# The stack
# ---------------------------------------------------------------------------

class Grabby(Strategy):
    """Records every position it was shown, so isolation can be asserted."""

    timeframe = "2h"
    lookback = 50

    def __init__(self, name: str) -> None:
        self.name = name
        self.seen: list[str] = []

    def evaluate(self, context):
        self.seen = [p.ticket for p in context.open_positions]
        return []


class Exploder(Strategy):
    timeframe = "2h"
    lookback = 50
    name = "boom"

    def evaluate(self, context):
        raise RuntimeError("bad strategy")


def position(ticket: str, owner: str) -> Position:
    return Position(
        ticket=ticket, symbol="XAUUSD", side=OrderSide.BUY, lots=0.1,
        entry_price=2000.0, stop_loss=1990.0, take_profit=None,
        opened_at=NOW, comment=owner,
    )


def context_with(positions, bars=None) -> StrategyContext:
    from tradebot.brokers.base import AccountSnapshot
    from tradebot.instruments import Instrument
    from tradebot.risk.limits import RiskLimits, RiskManager

    return StrategyContext(
        symbol="XAUUSD",
        instrument=Instrument(symbol="XAUUSD", contract_size=100.0, tick_size=0.01,
                              min_lot=0.01, max_lot=100.0, lot_step=0.01,
                              base_currency="XAU", quote_currency="USD", digits=2),
        candles=bars or candles([2000.0] * 60),
        bid=2000.0,
        ask=2000.2,
        account=AccountSnapshot(balance=10_000.0, equity=10_000.0, currency="USD",
                                margin_used=0.0, margin_free=10_000.0),
        open_positions=positions,
        news=None,
        risk=RiskManager(RiskLimits()),
        now=NOW,
    )


def test_each_strategy_sees_only_its_own_positions(tmp_path):
    a, b = Grabby("a"), Grabby("b")
    manager = PortfolioManager(
        roster=[a, b], journal=TradeJournal(tmp_path / "j.jsonl"),
        state_path=tmp_path / "p.json",
    )
    stack = StrategyStack(manager)
    stack.evaluate(context_with([position("1", "a"), position("2", "b"),
                                 position("3", "a")]))
    assert a.seen == ["1", "3"]
    assert b.seen == ["2"]


def test_untagged_positions_belong_to_nobody(tmp_path):
    """A hand-placed trade is not the bot's to manage."""
    a = Grabby("a")
    manager = PortfolioManager(
        roster=[a], journal=TradeJournal(tmp_path / "j.jsonl"),
        state_path=tmp_path / "p.json",
    )
    StrategyStack(manager).evaluate(context_with([position("manual", "")]))
    assert a.seen == []


def test_one_broken_strategy_does_not_stop_the_others(tmp_path):
    good = Grabby("good")
    manager = PortfolioManager(
        roster=[Exploder(), good], journal=TradeJournal(tmp_path / "j.jsonl"),
        state_path=tmp_path / "p.json",
    )
    StrategyStack(manager).evaluate(context_with([position("1", "good")]))
    assert good.seen == ["1"]


def test_benched_strategies_get_no_say(tmp_path):
    a, b = Grabby("a"), Grabby("b")
    journal = TradeJournal(tmp_path / "j.jsonl")
    manager = PortfolioManager(roster=[a, b], journal=journal,
                               state_path=tmp_path / "p.json", min_trades=5)
    write_trades(journal, "a", [-10.0] * 10)
    manager.review(now=NOW)

    StrategyStack(manager).evaluate(context_with([position("1", "a"),
                                                  position("2", "b")]))
    assert a.seen == []          # benched, never consulted
    assert b.seen == ["2"]


def test_mixed_timeframes_are_refused(tmp_path):
    slow, fast = Dummy("slow"), Dummy("fast")
    fast.timeframe = "15m"
    manager = PortfolioManager(
        roster=[slow, fast], journal=TradeJournal(tmp_path / "j.jsonl"),
        state_path=tmp_path / "p.json",
    )
    with pytest.raises(ValueError, match="share a timeframe"):
        StrategyStack(manager)


# ---------------------------------------------------------------------------
# The strategies themselves
# ---------------------------------------------------------------------------

def test_breakout_enters_on_a_new_high_in_an_uptrend():
    rising = [1000.0 + i * 2.0 for i in range(260)]
    rising[-1] = rising[-2] + 40.0                    # decisive break
    actions = BreakoutRider().evaluate(context_with([], candles(rising)))
    entries = [a for a in actions if isinstance(a, Enter)]
    assert len(entries) == 1
    assert entries[0].side is OrderSide.BUY
    assert entries[0].comment == "breakout_rider"


def test_breakout_never_goes_short():
    """Shorts lost on every market tested; the strategy must not offer them."""
    falling = [2000.0 - i * 2.0 for i in range(260)]
    actions = BreakoutRider().evaluate(context_with([], candles(falling)))
    assert [a for a in actions if isinstance(a, Enter)] == []


def test_breakout_stop_sits_below_entry_by_the_atr_multiple():
    rising = [1000.0 + i * 2.0 for i in range(260)]
    rising[-1] = rising[-2] + 40.0
    bars = candles(rising)
    entry = [a for a in BreakoutRider().evaluate(context_with([], bars))
             if isinstance(a, Enter)][0]
    assert entry.stop_loss < bars[-1].close


def test_no_second_entry_while_already_holding():
    rising = [1000.0 + i * 2.0 for i in range(260)]
    rising[-1] = rising[-2] + 40.0
    held = [position("1", "breakout_rider")]
    actions = BreakoutRider().evaluate(context_with(held, candles(rising)))
    assert [a for a in actions if isinstance(a, Enter)] == []


def test_winner_is_part_banked_and_stop_moves_to_breakeven():
    """Banking 30% is what lifted the win rate from 36.6% to 54.8%."""
    from tradebot.strategy.base import AdjustStop

    bars = candles([1000.0 + i * 2.0 for i in range(260)])
    held = Position(
        ticket="1", symbol="XAUUSD", side=OrderSide.BUY, lots=1.0,
        entry_price=1000.0,          # far below current price: deep in profit
        stop_loss=980.0, take_profit=None, opened_at=NOW,
        comment="breakout_rider",
    )
    ctx = context_with([held], bars)
    actions = BreakoutRider().evaluate(ctx)

    exits = [a for a in actions if isinstance(a, Exit) and a.reason == "bank-partial"]
    moves = [a for a in actions if isinstance(a, AdjustStop)]
    assert len(exits) == 1
    assert exits[0].lots == pytest.approx(0.3)
    assert moves and moves[0].stop_loss == pytest.approx(held.entry_price)


def test_banked_position_trails_but_never_loosens_the_stop():
    from tradebot.strategy.base import AdjustStop

    bars = candles([1000.0 + i * 2.0 for i in range(260)])
    # stop >= entry marks it as already banked
    held = Position(
        ticket="1", symbol="XAUUSD", side=OrderSide.BUY, lots=0.7,
        entry_price=1000.0, stop_loss=1999.0, take_profit=None,
        opened_at=NOW, comment="breakout_rider",
    )
    ctx = context_with([held], bars)
    ctx.bid = 1400.0                      # well below the existing stop
    actions = [a for a in BreakoutRider().evaluate(ctx) if isinstance(a, AdjustStop)]
    assert actions == []                  # would have been a loosening; refused


def test_kama_requires_a_sustained_rise_before_buying():
    """A single up-tick after chop must not qualify as a trend."""
    choppy = [100.0 + (2.0 if i % 2 else -2.0) for i in range(120)]
    choppy[-1] = 130.0
    actions = KamaTrend().evaluate(context_with([], candles(choppy)))
    assert [a for a in actions if isinstance(a, Enter)] == []


def staircase() -> list[float]:
    """An uptrend that dips, recovers for ten bars, then breaks to a new high."""
    prices = [100.0 + i * 1.0 for i in range(140)]
    for j in range(118, 123):
        prices[j] -= 14.0                                   # the pullback
    for j in range(123, 139):
        prices[j] = prices[122] + (j - 122) * 2.0           # the recovery
    prices[139] = prices[138] + 14.0                        # the breakout
    return prices


def test_kama_enters_a_breakout_that_followed_a_pullback():
    actions = KamaTrend().evaluate(context_with([], candles(staircase())))
    entries = [a for a in actions if isinstance(a, Enter)]
    assert len(entries) == 1
    assert entries[0].comment == "kama_trend"


def test_kama_refuses_a_vertical_run_with_no_pullback():
    """Don't buy the fifth straight bar up -- that is what the filter is for."""
    vertical = [100.0 + i * 1.5 for i in range(140)]
    vertical[-1] = vertical[-2] + 12.0
    actions = KamaTrend().evaluate(context_with([], candles(vertical)))
    assert [a for a in actions if isinstance(a, Enter)] == []


def test_strategies_stand_aside_during_news():
    from tradebot.news.calendar import NewsWindow

    rising = [1000.0 + i * 2.0 for i in range(260)]
    rising[-1] = rising[-2] + 40.0
    ctx = context_with([], candles(rising))
    ctx.news = NewsWindow(event=None, seconds_until=30.0,
                          is_imminent=True, is_fresh=False)
    actions = BreakoutRider().evaluate(ctx)
    assert [a for a in actions if isinstance(a, Enter)] == []


def test_short_history_is_handled_not_crashed():
    assert BreakoutRider().evaluate(context_with([], candles([100.0] * 5))) == []
    assert KamaTrend().evaluate(context_with([], candles([100.0] * 5))) == []


# ---------------------------------------------------------------------------
# Journal baseline — the books must start from the broker's number
# ---------------------------------------------------------------------------

def test_the_journal_baselines_itself_from_the_broker(tmp_path):
    """Seeded from a flag, the books start at a number that has nothing to do
    with the real account, and every reconciliation after that screams about a
    mismatch that is really a mis-seeded constant."""
    journal = TradeJournal(tmp_path / "j.jsonl", starting_balance=10_000.0)
    journal.ensure_baseline(2_635.39)

    assert journal.expected_balance() == pytest.approx(2_635.39)
    assert journal.reconcile(2_635.39).matches


def test_the_baseline_is_written_once_and_only_once(tmp_path):
    journal = TradeJournal(tmp_path / "j.jsonl")
    journal.ensure_baseline(2_635.39)
    journal.ensure_baseline(9_999.99)          # later balances must not move it
    assert journal.expected_balance() == pytest.approx(2_635.39)


def test_the_baseline_row_does_not_pollute_the_trade_list(tmp_path):
    journal = TradeJournal(tmp_path / "j.jsonl")
    journal.ensure_baseline(2_635.39)
    assert journal.entries() == []

    write_trades(journal, "gold_scalper", [12.0, -8.0])
    assert len(journal.entries()) == 2
    assert journal.expected_balance() == pytest.approx(2_635.39 + 4.0)
