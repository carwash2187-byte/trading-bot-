"""The Big-Runner strategy and the two indicators it needs.

Supertrend and MACD are worth testing directly rather than only through the
strategy: both have a convention that is easy to get backwards (Supertrend's
inverted direction, MACD's signal line starting late), and a sign error there
would be invisible in a strategy test that merely checked "it traded".
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

from tradebot.brokers.base import AccountSnapshot, Candle, OrderSide, Position
from tradebot.data.indicators import atr, macd, supertrend
from tradebot.instruments import Instrument
from tradebot.risk.limits import RiskLimits, RiskManager
from tradebot.strategy.base import AdjustStop, Enter, Exit, StrategyContext
from tradebot.strategy.runner import BigRunner

NOW = datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc)


def candles(closes: list[float], spread: float = 1.0) -> list[Candle]:
    return [
        Candle(
            timestamp=NOW - timedelta(hours=2 * (len(closes) - i)),
            open=close, high=close + spread, low=close - spread,
            close=close, volume=100.0,
        )
        for i, close in enumerate(closes)
    ]


def context_with(bars, positions=None, bid=None, ask=None) -> StrategyContext:
    last = bars[-1].close
    return StrategyContext(
        symbol="BTCUSD",
        instrument=Instrument(symbol="BTCUSD", contract_size=1.0, tick_size=0.01,
                              min_lot=0.001, max_lot=100.0, lot_step=0.001,
                              base_currency="BTC", quote_currency="USD", digits=2),
        candles=bars,
        bid=bid if bid is not None else last,
        ask=ask if ask is not None else last,
        account=AccountSnapshot(balance=10_000.0, equity=10_000.0, currency="USD",
                                margin_used=0.0, margin_free=10_000.0),
        open_positions=positions or [],
        news=None,
        risk=RiskManager(RiskLimits()),
        now=NOW,
    )


def market(bars: int = 900, seed: int = 7, drift: float = 0.0012) -> list[Candle]:
    """A noisy up-drifting chart, seeded so every run sees the same market.

    Straight synthetic ramps are useless for this strategy: on a perfectly
    smooth line Supertrend flips within a bar of the low while MACD is still
    deeply negative, so the two never agree and no entry can ever fire. Real
    charts are choppy, the flip gets delayed, and MACD catches up -- which is
    the situation the entry rules were actually written for.
    """
    rng = random.Random(seed)
    price = 100.0
    out = []
    for i in range(bars):
        price *= 1 + rng.gauss(drift, 0.018)
        out.append(
            Candle(
                timestamp=NOW - timedelta(hours=2 * (bars - i)),
                open=price, high=price * 1.006, low=price * 0.994,
                close=price, volume=100.0,
            )
        )
    return out


def window_ending_at_a_signal(bars: list[Candle], side: OrderSide) -> list[Candle]:
    """Cut the chart so the last bar is one where BigRunner wants to trade."""
    runner = BigRunner()
    for end in range(len(bars), 150, -1):
        actions = runner.evaluate(context_with(bars[:end]))
        entries = [a for a in actions if isinstance(a, Enter) and a.side == side]
        if entries:
            return bars[:end]
    raise AssertionError(f"no {side} signal in this market")


def position(side=OrderSide.BUY, entry=1000.0, stop=990.0, owner="big_runner"):
    return Position(
        ticket="t1", symbol="BTCUSD", side=side, lots=0.1, entry_price=entry,
        stop_loss=stop, take_profit=None, opened_at=NOW, comment=owner,
    )


# ---------------------------------------------------------------------------
# MACD
# ---------------------------------------------------------------------------

def test_macd_is_the_gap_between_the_two_averages(tmp_path=None):
    bars = candles([100.0 + i for i in range(80)])
    lines = macd(bars)
    # Rising market: the fast average leads, so the gap is positive.
    assert lines.macd[-1] > 0
    assert lines.histogram[-1] == lines.macd[-1] - lines.signal[-1]


def test_macd_signal_starts_after_the_macd_line_not_before():
    bars = candles([100.0 + i for i in range(80)])
    lines = macd(bars, fast=12, slow=26, signal=9)
    first_macd = next(i for i, v in enumerate(lines.macd) if v is not None)
    first_signal = next(i for i, v in enumerate(lines.signal) if v is not None)
    assert first_macd == 25                     # slow EMA seeds at bar 25
    assert first_signal == first_macd + 8       # then 9 bars of signal EMA


def test_macd_output_stays_aligned_to_the_bars():
    bars = candles([100.0 + i for i in range(80)])
    lines = macd(bars)
    assert len(lines.macd) == len(lines.signal) == len(lines.histogram) == 80


def test_macd_turns_negative_when_the_market_does():
    bars = candles([100.0 + i for i in range(60)] + [160.0 - 3 * i for i in range(40)])
    assert macd(bars).macd[-1] < 0


# ---------------------------------------------------------------------------
# Supertrend — the direction convention is inverted and easy to get wrong
# ---------------------------------------------------------------------------

def test_supertrend_says_minus_one_in_an_uptrend():
    """-1 is up. Backwards-looking, but it is what TradingView returns."""
    st = supertrend(candles([100.0 + i * 2 for i in range(80)]), 1.5, 14)
    assert st.direction[-1] == -1.0


def test_supertrend_says_plus_one_in_a_downtrend():
    st = supertrend(candles([300.0 - i * 2 for i in range(80)]), 1.5, 14)
    assert st.direction[-1] == 1.0


def test_supertrend_line_sits_below_price_in_an_uptrend():
    bars = candles([100.0 + i * 2 for i in range(80)])
    st = supertrend(bars, 1.5, 14)
    assert st.line[-1] < bars[-1].close


def test_the_line_ratchets_and_never_backs_away_from_price():
    """The one-way band is the whole indicator; a loose band would whipsaw.

    Only true *within* one trend. At a flip the line jumps to the other band,
    which is the flip, not a failure of the ratchet.
    """
    bars = market()
    st = supertrend(bars, 1.5, 14)
    checked = 0
    for i in range(1, len(bars)):
        if st.line[i] is None or st.line[i - 1] is None:
            continue
        if st.direction[i] != st.direction[i - 1]:
            continue                             # the flip itself
        if st.direction[i] == -1.0:              # uptrend: line only rises
            assert st.line[i] >= st.line[i - 1]
        else:                                    # downtrend: line only falls
            assert st.line[i] <= st.line[i - 1]
        checked += 1
    assert checked > 500                         # the assertions actually ran


def test_flip_fires_once_at_the_turn_not_for_the_whole_trend():
    down_then_up = [300.0 - i * 3 for i in range(60)] + [120.0 + i * 4 for i in range(60)]
    st = supertrend(candles(down_then_up), 1.5, 14)
    flips = [i for i in range(len(st.direction)) if st.flipped_up(i)]
    assert len(flips) == 1
    assert 55 < flips[0] < 75          # right around the turn


def test_flip_helpers_are_safe_at_the_edges():
    st = supertrend(candles([100.0] * 30), 1.5, 14)
    assert st.flipped_up(0) is False
    assert st.flipped_up(9999) is False


# ---------------------------------------------------------------------------
# Entry — all three conditions must agree
# ---------------------------------------------------------------------------

def test_it_buys_when_the_trend_turns_up():
    window = window_ending_at_a_signal(market(), OrderSide.BUY)
    entries = [
        a for a in BigRunner().evaluate(context_with(window)) if isinstance(a, Enter)
    ]
    assert len(entries) == 1
    assert entries[0].side == OrderSide.BUY
    assert entries[0].comment == "big_runner"


def test_it_will_also_short():
    """Shorts were part of what was validated, unlike the trend.py strategies."""
    window = window_ending_at_a_signal(market(drift=-0.0012), OrderSide.SELL)
    entries = [
        a for a in BigRunner().evaluate(context_with(window)) if isinstance(a, Enter)
    ]
    assert entries[0].side == OrderSide.SELL
    assert entries[0].stop_loss > window[-1].close      # stop sits above a short


def test_it_ignores_most_bars():
    """A signal on every bar would mean the filters are not filtering."""
    bars = market()
    runner = BigRunner()
    signals = sum(
        1
        for end in range(200, len(bars))
        if any(isinstance(a, Enter) for a in runner.evaluate(context_with(bars[:end])))
    )
    assert 0 < signals < len(bars) * 0.1


def test_the_stop_goes_where_the_volatility_says():
    window = window_ending_at_a_signal(market(), OrderSide.BUY)
    entry = [
        a for a in BigRunner().evaluate(context_with(window)) if isinstance(a, Enter)
    ][0]
    expected = window[-1].close - 1.5 * atr(window, 14)[-1]
    assert abs(entry.stop_loss - expected) < 1e-9
    assert entry.stop_loss < window[-1].close


def test_it_stands_aside_during_news():
    class Blocking:
        active = True

    context = context_with(window_ending_at_a_signal(market(), OrderSide.BUY))
    context.news = Blocking()
    assert not [a for a in BigRunner().evaluate(context) if isinstance(a, Enter)]


def test_it_waits_until_there_is_enough_history():
    assert BigRunner().evaluate(context_with(candles([100.0] * 40))) == []


# ---------------------------------------------------------------------------
# The trail — lopsided on purpose
# ---------------------------------------------------------------------------

def test_the_trail_follows_price_up():
    bars = candles([100.0 + i for i in range(200)])
    open_pos = position(entry=150.0, stop=140.0)
    actions = BigRunner().evaluate(context_with(bars, [open_pos]))
    moves = [a for a in actions if isinstance(a, AdjustStop)]
    assert len(moves) == 1
    assert moves[0].stop_loss > 140.0


def test_the_trail_never_moves_back_toward_the_entry():
    """A stop that can retreat is not protection, it is a suggestion."""
    bars = candles([100.0 + i for i in range(200)])
    already_tight = position(entry=150.0, stop=bars[-1].close - 1.0)
    actions = BigRunner().evaluate(context_with(bars, [already_tight]))
    assert not [a for a in actions if isinstance(a, AdjustStop)]


def test_the_trail_is_much_wider_than_the_entry_stop():
    """The looseness is the strategy: a tight trail clips the runners."""
    runner = BigRunner()
    assert runner.trail_atr > runner.stop_atr * 4


def test_a_short_trails_downward():
    bars = candles([300.0 - i for i in range(200)])
    short = position(side=OrderSide.SELL, entry=250.0, stop=260.0)
    actions = BigRunner().evaluate(context_with(bars, [short]))
    moves = [a for a in actions if isinstance(a, AdjustStop)]
    assert len(moves) == 1
    assert moves[0].stop_loss < 260.0


# ---------------------------------------------------------------------------
# Staying in its lane
# ---------------------------------------------------------------------------

def test_it_leaves_other_strategies_positions_alone():
    bars = candles([100.0 + i for i in range(200)])
    theirs = position(entry=150.0, stop=140.0, owner="breakout_rider")
    actions = BigRunner().evaluate(context_with(bars, [theirs]))
    assert actions == []


def test_it_does_not_stack_a_second_trade_on_its_own_position():
    window = window_ending_at_a_signal(market(), OrderSide.BUY)
    held = position(entry=window[-1].close, stop=window[-1].close * 0.97)
    actions = BigRunner().evaluate(context_with(window, [held]))
    assert not [a for a in actions if isinstance(a, Enter)]


def test_it_exits_when_the_trend_flips_against_it():
    """The reason for holding is gone, so the wide trail no longer applies."""
    bars = market()
    st = supertrend(bars, 1.5, 14)
    turn = max(i for i in range(len(bars)) if st.flipped_down(i))
    window = bars[: turn + 1]

    held = position(entry=window[-1].close, stop=window[-1].close * 0.9)
    actions = BigRunner().evaluate(context_with(window, [held]))
    exits = [a for a in actions if isinstance(a, Exit)]
    assert len(exits) == 1
    assert exits[0].reason == "supertrend-flip"


def test_a_flip_the_other_way_does_not_panic_a_short_out():
    """A short should exit on an up-flip, not a down-flip."""
    bars = market()
    st = supertrend(bars, 1.5, 14)
    turn = max(i for i in range(len(bars)) if st.flipped_down(i))
    window = bars[: turn + 1]

    short = position(side=OrderSide.SELL, entry=window[-1].close,
                     stop=window[-1].close * 1.1)
    actions = BigRunner().evaluate(context_with(window, [short]))
    assert not [a for a in actions if isinstance(a, Exit)]
