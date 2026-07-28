"""The non-trend strategies.

What matters for these is not that they trade, but that they refuse to. Each
one has a specific market it must stand aside for -- fading a real breakout, or
buying every leg of a crash, is how this family of strategy destroys an account.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from tradebot.brokers.base import AccountSnapshot, Candle, OrderSide, Position
from tradebot.instruments import Instrument
from tradebot.risk.limits import RiskLimits, RiskManager
from tradebot.strategy.base import Enter, Exit, StrategyContext
from tradebot.strategy.reversion import MeanReverter, PullbackBuyer, RangeFader

NOW = datetime(2026, 7, 1, tzinfo=timezone.utc)


def candles(closes, spread=None) -> list[Candle]:
    out = []
    for i, close in enumerate(closes):
        wobble = spread if spread is not None else close * 0.004
        out.append(Candle(
            timestamp=NOW - timedelta(hours=2 * (len(closes) - i)),
            open=close, high=close + wobble, low=close - wobble,
            close=close, volume=100.0,
        ))
    return out


def context_with(bars, positions=None) -> StrategyContext:
    last = bars[-1].close
    return StrategyContext(
        symbol="BTCUSD",
        instrument=Instrument(symbol="BTCUSD", contract_size=1.0, tick_size=0.01,
                              min_lot=0.001, max_lot=100.0, lot_step=0.001,
                              base_currency="BTC", quote_currency="USD", digits=2),
        candles=bars, bid=last, ask=last,
        account=AccountSnapshot(balance=10_000.0, equity=10_000.0, currency="USD",
                                margin_used=0.0, margin_free=10_000.0),
        open_positions=positions or [],
        news=None, risk=RiskManager(RiskLimits()), now=NOW,
    )


def position(side=OrderSide.BUY, entry=1000.0, stop=990.0, owner="") -> Position:
    return Position(ticket="t1", symbol="BTCUSD", side=side, lots=0.1,
                    entry_price=entry, stop_loss=stop, take_profit=None,
                    opened_at=NOW, comment=owner)


def entries(actions):
    return [a for a in actions if isinstance(a, Enter)]


def exits(actions):
    return [a for a in actions if isinstance(a, Exit)]


# ---------------------------------------------------------------------------
# MeanReverter — must need a genuine extreme, not just a direction
# ---------------------------------------------------------------------------

def crashed() -> list[Candle]:
    """Calm, then a sudden drop.

    The suddenness is required, not decorative. A *steady* decline never breaks
    its own Bollinger band, because the band widens along with the move -- so a
    linear ramp down, however far it goes, is not a capitulation on this
    measure. Only a sharp move against a calm recent history is.
    """
    return candles([1000.0 + (i % 5) * 0.5 for i in range(140)]
                   + [1000.0 - 40.0 * i for i in range(1, 4)])


def test_it_buys_a_genuine_capitulation():
    bars = crashed()
    got = entries(MeanReverter().evaluate(context_with(bars)))
    assert len(got) == 1
    assert got[0].side == OrderSide.BUY
    assert got[0].stop_loss < bars[-1].close


def test_a_quiet_drift_down_is_not_a_signal():
    """A slow decline is a trend. Buying it is how this strategy dies."""
    drift = candles([1000.0 - i * 0.4 for i in range(200)])
    assert not entries(MeanReverter().evaluate(context_with(drift)))


def test_it_does_nothing_in_the_middle_of_the_range():
    calm = candles([1000.0 + (i % 7) for i in range(200)])
    assert not entries(MeanReverter().evaluate(context_with(calm)))


def test_it_takes_profit_back_at_the_average_not_past_it():
    """Reversion to the mean is reliable; past it is a new bet."""
    bars = candles([1000.0] * 150 + [960.0, 970.0, 985.0, 1000.0])
    held = position(entry=960.0, stop=940.0, owner="mean_reverter")
    assert len(exits(MeanReverter().evaluate(context_with(bars, [held])))) == 1


def test_shorts_can_be_switched_off():
    spiked = candles([1000.0 + (i % 5) * 0.5 for i in range(140)]
                     + [1000.0 + 40.0 * i for i in range(1, 4)])
    assert entries(MeanReverter().evaluate(context_with(spiked)))
    assert not entries(
        MeanReverter(allow_shorts=False).evaluate(context_with(spiked))
    )


# ---------------------------------------------------------------------------
# PullbackBuyer — the turn is the whole point
# ---------------------------------------------------------------------------

def dipped_and_turned() -> list[Candle]:
    seq = [500.0 + i * 2.5 for i in range(240)]      # established uptrend
    top = seq[-1]
    seq.append(top - 30)                             # dip to the short average
    seq.append(top - 45)                             # the low
    seq.append(top - 35)                             # and turning back up
    return candles(seq)


def test_it_buys_a_dip_that_has_stopped_falling():
    got = entries(PullbackBuyer().evaluate(context_with(dipped_and_turned())))
    assert len(got) == 1
    assert got[0].side == OrderSide.BUY


def test_it_will_not_buy_a_dip_that_is_still_falling():
    """Without requiring the turn, this buys every leg of a crash."""
    seq = [500.0 + i * 2.5 for i in range(240)]
    seq += [seq[-1] - 20 * i for i in range(1, 5)]   # still going down
    assert not entries(PullbackBuyer().evaluate(context_with(candles(seq))))


def test_it_does_not_buy_a_dip_in_a_downtrend():
    seq = [1200.0 - i * 2.5 for i in range(240)]
    seq += [seq[-1] - 30, seq[-1] - 10]
    assert not entries(PullbackBuyer().evaluate(context_with(candles(seq))))


def test_it_never_shorts():
    """Shorts lost on every market tested in this project."""
    seq = [1200.0 - i * 2.5 for i in range(260)]
    got = entries(PullbackBuyer().evaluate(context_with(candles(seq))))
    assert all(a.side == OrderSide.BUY for a in got)


def test_it_bails_when_the_trend_it_was_buying_is_gone():
    bars = candles([500.0 + i * 2.5 for i in range(240)] + [400.0])
    held = position(entry=1000.0, stop=980.0, owner="pullback_buyer")
    assert exits(PullbackBuyer().evaluate(context_with(bars, [held])))


# ---------------------------------------------------------------------------
# RangeFader — must stand aside when the market starts trending
# ---------------------------------------------------------------------------

def settling_range(start_amp: float = 60.0, end_amp: float = 15.0) -> list[Candle]:
    """A market whose swings are shrinking -- quiet by its own recent standard.

    A constant-amplitude wave will not do: the regime test compares this
    window's width to the widest recent window, so a perfect sine reads as
    100% of its own history and is correctly refused.
    """
    import math

    seq = []
    for i in range(300):
        amp = start_amp + (end_amp - start_amp) * (i / 299)
        seq.append(1000.0 + amp * math.sin(i / 6.0))
    seq[-1] = 1000.0 - end_amp * 0.95                # pushed to the low edge
    return candles(seq, spread=1.0)


def test_it_fades_the_bottom_of_a_quiet_range():
    got = entries(RangeFader().evaluate(context_with(settling_range())))
    assert got and got[0].side == OrderSide.BUY


def test_it_stands_aside_once_the_range_expands():
    """Fading a real breakout is how this strategy kills an account."""
    import math
    seq = [1000.0 + 20 * math.sin(i / 6.0) for i in range(200)]
    seq += [1000.0 + i * 12 for i in range(100)]     # volatility expands
    assert not entries(RangeFader().evaluate(context_with(candles(seq, spread=1.0))))


def test_a_steady_wave_is_not_quiet_by_its_own_standard():
    """Constant volatility is not a lull -- there is no edge to fade."""
    import math
    steady = candles([1000.0 + 20 * math.sin(i / 6.0) for i in range(300)],
                     spread=1.0)
    assert not entries(RangeFader().evaluate(context_with(steady)))


def test_it_waits_for_enough_history_to_judge_the_regime():
    assert RangeFader().evaluate(context_with(candles([1000.0] * 50))) == []


def test_it_leaves_another_strategys_position_alone():
    import math
    seq = [1000.0 + 20 * math.sin(i / 6.0) for i in range(300)]
    theirs = position(entry=1000.0, owner="big_runner")
    actions = RangeFader().evaluate(context_with(candles(seq, spread=1.0), [theirs]))
    assert not exits(actions)
    assert not entries(actions)
