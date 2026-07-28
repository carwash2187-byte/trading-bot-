"""Instrument specifications and the contract-multiplier maths.

Everything money-related in this package funnels through here. Brokers report
sizes in *lots*; profit and loss happens in *units*. Confusing the two is the
mistake that silently misstates every trade by up to 100,000x, so the
conversion lives in exactly one place and is covered by tests.

    units = lots * contract_size

For EURUSD one lot is 100,000 EUR. For XAUUSD one lot is 100 ounces. A 1.00
price move on a 1-lot XAUUSD position is $100, not $1 and not $100,000.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field


class InstrumentError(ValueError):
    """Raised when an instrument spec or a size is not usable."""


@dataclass(frozen=True)
class Instrument:
    """Static contract details for one tradable symbol.

    Attributes:
        symbol: Broker-facing symbol, e.g. ``"XAUUSD"``.
        contract_size: Units of the base asset in one standard lot.
        tick_size: Smallest price increment the broker quotes.
        min_lot / max_lot / lot_step: Broker volume constraints.
        base_currency / quote_currency: ``EURUSD`` -> base EUR, quote USD.
        digits: Price decimal places, used for rounding orders.
    """

    symbol: str
    contract_size: float
    tick_size: float
    min_lot: float
    max_lot: float
    lot_step: float
    base_currency: str
    quote_currency: str
    digits: int = 5
    description: str = ""
    # Symbols whose prices tend to move together. Used by the correlation cap.
    correlation_group: str | None = None

    def __post_init__(self) -> None:
        if self.contract_size <= 0:
            raise InstrumentError(f"{self.symbol}: contract_size must be > 0")
        if self.tick_size <= 0:
            raise InstrumentError(f"{self.symbol}: tick_size must be > 0")
        if self.lot_step <= 0:
            raise InstrumentError(f"{self.symbol}: lot_step must be > 0")
        if self.min_lot <= 0 or self.max_lot < self.min_lot:
            raise InstrumentError(f"{self.symbol}: invalid lot bounds")

    # -- conversions ----------------------------------------------------

    def units(self, lots: float) -> float:
        """Convert broker lots to base-asset units."""
        return lots * self.contract_size

    def lots(self, units: float) -> float:
        """Convert base-asset units back to broker lots."""
        return units / self.contract_size

    def round_price(self, price: float) -> float:
        """Snap a price to the instrument's tick grid."""
        ticks = round(price / self.tick_size)
        return round(ticks * self.tick_size, self.digits)

    def round_lots(self, lots: float) -> float:
        """Round volume DOWN to a valid lot step, then clamp to bounds.

        Rounding down matters: rounding up would quietly take more risk than
        the caller asked for. Returns 0.0 when the size is below ``min_lot``,
        which callers must treat as "do not trade".
        """
        if lots <= 0 or not math.isfinite(lots):
            return 0.0
        steps = math.floor(round(lots / self.lot_step, 9))
        stepped = steps * self.lot_step
        # Kill float dust like 0.30000000000000004.
        stepped = round(stepped, 9)
        if stepped < self.min_lot:
            return 0.0
        return min(stepped, self.max_lot)

    # -- money ----------------------------------------------------------

    def pnl_in_quote(self, entry: float, exit_: float, lots: float, is_long: bool) -> float:
        """Profit/loss in the *quote* currency for a closed position."""
        direction = 1.0 if is_long else -1.0
        return (exit_ - entry) * self.units(lots) * direction

    def pnl_in_account(
        self,
        entry: float,
        exit_: float,
        lots: float,
        is_long: bool,
        quote_to_account_rate: float = 1.0,
    ) -> float:
        """Profit/loss converted into the account's currency.

        ``quote_to_account_rate`` is how many account-currency units one unit
        of quote currency buys. For a USD account trading XAUUSD (quote USD)
        that is 1.0; for a USD account trading EURGBP (quote GBP) it is the
        GBPUSD rate.
        """
        if quote_to_account_rate <= 0:
            raise InstrumentError("quote_to_account_rate must be > 0")
        return self.pnl_in_quote(entry, exit_, lots, is_long) * quote_to_account_rate

    def value_per_price_unit(self, lots: float, quote_to_account_rate: float = 1.0) -> float:
        """Account-currency value of a 1.00 price move at this size."""
        return self.units(lots) * quote_to_account_rate


# ---------------------------------------------------------------------------
# A small default catalogue. Real deployments should refresh these from the
# broker at startup (see Broker.get_instrument) rather than trusting constants.
# ---------------------------------------------------------------------------

DEFAULT_INSTRUMENTS: dict[str, Instrument] = {
    "EURUSD": Instrument(
        symbol="EURUSD", contract_size=100_000, tick_size=0.00001,
        min_lot=0.01, max_lot=100.0, lot_step=0.01,
        base_currency="EUR", quote_currency="USD", digits=5,
        description="Euro vs US Dollar", correlation_group="EUR",
    ),
    "GBPUSD": Instrument(
        symbol="GBPUSD", contract_size=100_000, tick_size=0.00001,
        min_lot=0.01, max_lot=100.0, lot_step=0.01,
        base_currency="GBP", quote_currency="USD", digits=5,
        description="Pound vs US Dollar", correlation_group="GBP",
    ),
    "USDJPY": Instrument(
        symbol="USDJPY", contract_size=100_000, tick_size=0.001,
        min_lot=0.01, max_lot=100.0, lot_step=0.01,
        base_currency="USD", quote_currency="JPY", digits=3,
        description="US Dollar vs Yen", correlation_group="JPY",
    ),
    "XAUUSD": Instrument(
        symbol="XAUUSD", contract_size=100, tick_size=0.01,
        min_lot=0.01, max_lot=50.0, lot_step=0.01,
        base_currency="XAU", quote_currency="USD", digits=2,
        description="Gold vs US Dollar (100 oz per lot)", correlation_group="METALS",
    ),
    "BTCUSD": Instrument(
        symbol="BTCUSD", contract_size=1, tick_size=0.01,
        min_lot=0.01, max_lot=10.0, lot_step=0.01,
        base_currency="BTC", quote_currency="USD", digits=2,
        description="Bitcoin vs US Dollar (1 coin per lot)", correlation_group="CRYPTO",
    ),
}


def get_instrument(symbol: str) -> Instrument:
    """Look up a built-in instrument spec, case-insensitively."""
    try:
        return DEFAULT_INSTRUMENTS[symbol.upper()]
    except KeyError:
        raise InstrumentError(
            f"unknown instrument {symbol!r}; register it in DEFAULT_INSTRUMENTS "
            f"or fetch it from the broker with Broker.get_instrument()"
        ) from None
