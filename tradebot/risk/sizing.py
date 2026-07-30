"""Position sizing driven by account equity and risk-per-trade.

The whole point: decide size from how far away the stop is, never from a fixed
lot number. A wide stop gets a small position, a tight stop gets a larger one,
and the dollar risk stays the same either way.

    risk_dollars  = equity * risk_pct
    units         = risk_dollars / (stop_distance * quote_to_account_rate)
    lots          = round_down(units / contract_size)

Rounding is always DOWN, so the realised risk can only ever come in under the
target, never over it.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..instruments import Instrument


class SizingError(ValueError):
    """Raised when a size cannot be computed safely."""


@dataclass(frozen=True)
class SizedTrade:
    """The result of a sizing calculation."""

    lots: float
    units: float
    risk_amount: float          # what we intend to lose if the stop hits
    actual_risk: float          # what we will lose after lot rounding
    stop_distance: float
    tradable: bool
    # Why the size was refused, when it was. A bare False is not enough: a
    # refusal that carries no reason is indistinguishable from a strategy with no
    # signal, and that is exactly how every JPY-quoted pair came to silently
    # never trade in this project.
    reason: str = ""

    @property
    def rejected(self) -> bool:
        return not self.tradable


def size_position(
    instrument: Instrument,
    equity: float,
    risk_pct: float,
    entry_price: float,
    stop_price: float,
    quote_to_account_rate: float = 1.0,
    max_lots: float | None = None,
) -> SizedTrade:
    """Work out how many lots risks ``risk_pct`` of ``equity`` on this stop.

    Args:
        instrument: Contract spec; supplies the lot/unit multiplier.
        equity: Current account equity in the account currency.
        risk_pct: Fraction of equity to risk, e.g. ``0.01`` for 1%.
        entry_price: Intended entry.
        stop_price: Protective stop. Must differ from the entry.
        quote_to_account_rate: Quote currency -> account currency rate.
        max_lots: Optional hard cap applied before broker limits.

    Returns:
        A :class:`SizedTrade`. Check ``tradable`` before submitting: a size
        below the broker's minimum lot comes back as ``lots=0`` rather than
        being silently rounded up into more risk than requested.
    """
    if equity <= 0:
        raise SizingError("equity must be > 0")
    if not 0 < risk_pct < 1:
        raise SizingError("risk_pct must be a fraction between 0 and 1")
    if quote_to_account_rate <= 0:
        raise SizingError("quote_to_account_rate must be > 0")

    stop_distance = abs(entry_price - stop_price)
    if stop_distance <= 0:
        raise SizingError("stop_price must differ from entry_price")
    if stop_distance < instrument.tick_size:
        raise SizingError(
            f"stop is {stop_distance} away, closer than one tick "
            f"({instrument.tick_size}) — refusing to size this"
        )

    risk_amount = equity * risk_pct
    # Value of a 1.00 price move on ONE unit, in account currency.
    value_per_unit = quote_to_account_rate
    raw_units = risk_amount / (stop_distance * value_per_unit)
    raw_lots = instrument.lots(raw_units)

    if max_lots is not None:
        raw_lots = min(raw_lots, max_lots)

    lots = instrument.round_lots(raw_lots)
    if lots <= 0:
        why = (
            f"{instrument.symbol}: wanted {raw_lots:.6f} lots, below the "
            f"{instrument.min_lot} minimum"
        )
        # The overwhelmingly common cause is a missing currency conversion. A
        # yen-quoted pair whose quote_to_account_rate is left at 1.0 values every
        # pip about 150x too highly, so the sizer asks for a fraction of the
        # minimum lot and the trade is refused -- on every single signal, forever.
        if quote_to_account_rate == 1.0 and instrument.quote_currency not in (
            "USD", instrument.base_currency
        ):
            why += (
                f" -- quote currency is {instrument.quote_currency} but "
                f"quote_to_account_rate is 1.0, which is almost certainly a "
                f"missing conversion"
            )
        return SizedTrade(
            lots=0.0,
            units=0.0,
            risk_amount=risk_amount,
            actual_risk=0.0,
            stop_distance=stop_distance,
            tradable=False,
            reason=why,
        )

    units = instrument.units(lots)
    actual_risk = stop_distance * units * value_per_unit
    return SizedTrade(
        lots=lots,
        units=units,
        risk_amount=risk_amount,
        actual_risk=actual_risk,
        stop_distance=stop_distance,
        tradable=True,
    )


def risk_of_position(
    instrument: Instrument,
    lots: float,
    entry_price: float,
    stop_price: float,
    quote_to_account_rate: float = 1.0,
) -> float:
    """Account-currency loss if this position's stop is hit."""
    return abs(entry_price - stop_price) * instrument.units(lots) * quote_to_account_rate
