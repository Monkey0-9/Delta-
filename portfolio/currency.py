"""Currency exposure: convert positions to base currency and cap exposures."""
from __future__ import annotations

from decimal import Decimal
from typing import Mapping


def to_base_currency(
    positions: Mapping[str, Decimal],
    currencies: Mapping[str, str],
    fx_to_base: Mapping[str, Decimal],
    base: str = "USD",
) -> dict[str, Decimal]:
    """Convert each position to base currency. Missing FX is fail-closed."""
    out: dict[str, Decimal] = {}
    for asset, qty in positions.items():
        ccy = currencies.get(asset, base)
        if ccy == base:
            out[asset] = qty
            continue
        if ccy not in fx_to_base:
            raise ValueError(f"missing FX rate for {ccy}.")
        out[asset] = qty * fx_to_base[ccy]
    return out


def currency_exposure(
    base_positions: Mapping[str, Decimal], currencies: Mapping[str, str], base: str = "USD"
) -> dict[str, Decimal]:
    """Aggregate base-currency exposure by currency bucket."""
    totals: dict[str, Decimal] = {}
    for asset, value in base_positions.items():
        ccy = currencies.get(asset, base)
        totals[ccy] = totals.get(ccy, Decimal("0")) + abs(value)
    return totals


def check_currency_caps(exposure: Mapping[str, Decimal], caps: Mapping[str, Decimal]) -> tuple[str, ...]:
    return tuple(sorted(c for c, total in exposure.items() if c in caps and total > caps[c]))
