"""Position sizing and the lot/contract-multiplier maths.

This is the file that matters most. A bug here misstates every trade's dollar
result, often by a factor of 100,000, and nothing downstream would notice.
"""

from __future__ import annotations

import pytest

from tradebot.instruments import Instrument, get_instrument
from tradebot.risk.sizing import SizingError, risk_of_position, size_position


# -- the multiplier itself --------------------------------------------------

def test_forex_lot_is_100k_units():
    eurusd = get_instrument("EURUSD")
    assert eurusd.units(1.0) == 100_000
    assert eurusd.units(0.1) == 10_000
    assert eurusd.lots(100_000) == 1.0


def test_gold_lot_is_100_ounces_not_100k():
    """The classic trap: gold is 100 oz per lot, not 100,000."""
    gold = get_instrument("XAUUSD")
    assert gold.units(1.0) == 100
    # A $1.00 move on one lot of gold is $100.
    assert gold.pnl_in_quote(2000.0, 2001.0, 1.0, is_long=True) == pytest.approx(100.0)


def test_one_pip_on_one_standard_lot_eurusd_is_ten_dollars():
    eurusd = get_instrument("EURUSD")
    pnl = eurusd.pnl_in_quote(1.10000, 1.10010, 1.0, is_long=True)
    assert pnl == pytest.approx(10.0)


def test_short_pnl_is_inverted():
    eurusd = get_instrument("EURUSD")
    long_pnl = eurusd.pnl_in_quote(1.1000, 1.1050, 1.0, is_long=True)
    short_pnl = eurusd.pnl_in_quote(1.1000, 1.1050, 1.0, is_long=False)
    assert long_pnl == pytest.approx(500.0)
    assert short_pnl == pytest.approx(-500.0)


def test_currency_conversion_applied_to_pnl():
    """A GBP-quoted pair on a USD account must convert, not assume 1:1."""
    inst = Instrument(
        symbol="EURGBP", contract_size=100_000, tick_size=0.00001,
        min_lot=0.01, max_lot=100.0, lot_step=0.01,
        base_currency="EUR", quote_currency="GBP",
    )
    quote_pnl = inst.pnl_in_quote(0.8500, 0.8550, 1.0, is_long=True)
    assert quote_pnl == pytest.approx(500.0)          # 500 GBP
    account_pnl = inst.pnl_in_account(0.8500, 0.8550, 1.0, True, quote_to_account_rate=1.27)
    assert account_pnl == pytest.approx(635.0)        # 500 GBP -> 635 USD


# -- lot rounding -----------------------------------------------------------

def test_lots_round_down_never_up():
    """Rounding up would take more risk than the caller asked for."""
    eurusd = get_instrument("EURUSD")
    assert eurusd.round_lots(0.019) == pytest.approx(0.01)
    assert eurusd.round_lots(0.999) == pytest.approx(0.99)


def test_size_below_minimum_is_rejected_not_rounded_up():
    eurusd = get_instrument("EURUSD")
    assert eurusd.round_lots(0.004) == 0.0


def test_lots_clamped_to_broker_maximum():
    eurusd = get_instrument("EURUSD")
    assert eurusd.round_lots(500.0) == pytest.approx(100.0)


# -- sizing -----------------------------------------------------------------

def test_risk_is_capped_at_the_requested_percentage():
    eurusd = get_instrument("EURUSD")
    sized = size_position(
        instrument=eurusd, equity=10_000.0, risk_pct=0.01,
        entry_price=1.1000, stop_price=1.0950,      # 50 pip stop
    )
    assert sized.tradable
    # 1% of 10k = $100 at risk; rounding down means never more than that.
    assert sized.actual_risk <= 100.0 + 1e-9
    assert sized.actual_risk == pytest.approx(100.0, abs=5.0)


def test_wider_stop_gives_smaller_position():
    """The dollar risk is held constant; only the size moves."""
    eurusd = get_instrument("EURUSD")
    tight = size_position(eurusd, 10_000.0, 0.01, 1.1000, 1.0990)   # 10 pips
    wide = size_position(eurusd, 10_000.0, 0.01, 1.1000, 1.0900)    # 100 pips
    assert tight.lots > wide.lots
    assert tight.actual_risk == pytest.approx(wide.actual_risk, abs=12.0)


def test_gold_sizing_uses_the_right_multiplier():
    """With contract_size=100, a $10 stop and $100 risk gives 0.10 lots."""
    gold = get_instrument("XAUUSD")
    sized = size_position(gold, 10_000.0, 0.01, 2000.0, 1990.0)
    assert sized.lots == pytest.approx(0.10)
    assert sized.actual_risk == pytest.approx(100.0)


def test_risk_scales_with_equity():
    eurusd = get_instrument("EURUSD")
    small = size_position(eurusd, 10_000.0, 0.01, 1.1000, 1.0950)
    large = size_position(eurusd, 100_000.0, 0.01, 1.1000, 1.0950)
    assert large.lots == pytest.approx(small.lots * 10, rel=0.02)


def test_tiny_account_rejects_rather_than_oversizing():
    """A $50 account cannot risk 1% on a 100-pip stop at the minimum lot."""
    eurusd = get_instrument("EURUSD")
    sized = size_position(eurusd, 50.0, 0.01, 1.1000, 1.0900)
    assert sized.rejected
    assert sized.lots == 0.0


def test_zero_stop_distance_is_an_error():
    eurusd = get_instrument("EURUSD")
    with pytest.raises(SizingError):
        size_position(eurusd, 10_000.0, 0.01, 1.1000, 1.1000)


def test_sub_tick_stop_is_an_error():
    """A stop closer than one tick would imply an absurd position size."""
    eurusd = get_instrument("EURUSD")
    with pytest.raises(SizingError):
        size_position(eurusd, 10_000.0, 0.01, 1.10000, 1.100001)


@pytest.mark.parametrize("bad_pct", [0.0, 1.0, -0.5, 5.0])
def test_risk_pct_must_be_a_fraction(bad_pct):
    eurusd = get_instrument("EURUSD")
    with pytest.raises(SizingError):
        size_position(eurusd, 10_000.0, bad_pct, 1.1000, 1.0950)


def test_risk_of_position_matches_sizing():
    """Round trip: size a trade, then re-derive its risk independently."""
    gold = get_instrument("XAUUSD")
    sized = size_position(gold, 25_000.0, 0.02, 2400.0, 2380.0)
    recomputed = risk_of_position(gold, sized.lots, 2400.0, 2380.0)
    assert recomputed == pytest.approx(sized.actual_risk)
