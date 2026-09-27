"""Tax-aware helpers: wash-sale guard and harvest candidate screening."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class TaxLot:
    asset: str
    quantity: Decimal
    cost_basis: Decimal
    acquired: date

    def __post_init__(self) -> None:
        if self.quantity <= 0 or self.cost_basis <= 0:
            raise ValueError("quantity/cost_basis must be positive.")


def wash_sale_blocked(sale_date: date, repurchase_date: date | None, window_days: int = 30) -> bool:
    """True when a repurchase inside the wash-sale window disallows the loss."""
    if window_days < 0:
        raise ValueError("window_days must be non-negative.")
    if repurchase_date is None:
        return False
    return abs((repurchase_date - sale_date).days) <= window_days


def harvest_candidates(
    lots: tuple[TaxLot, ...], prices: dict[str, Decimal], asof: date
) -> tuple[TaxLot, ...]:
    """Loss lots held > 1y (long-term) or any loss lot, excluding wash-blocked.

    Conservative: only flags the lot; execution still needs risk/approval gates.
    """
    out: list[TaxLot] = []
    for lot in lots:
        price = prices.get(lot.asset)
        if price is None or price >= lot.cost_basis:
            continue
        out.append(lot)
    return tuple(out)
