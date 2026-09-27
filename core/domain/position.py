from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from .price import Price
from .quantity import Quantity


@dataclass(frozen=True, slots=True)
class Position:
    instrument_id: UUID
    quantity: Quantity
    average_price: Price
    current_price: Price

    @property
    def market_value(self) -> Decimal:
        return self.quantity.value * self.current_price.value

    @property
    def cost_basis(self) -> Decimal:
        return self.quantity.value * self.average_price.value

    @property
    def unrealized_pnl(self) -> Decimal:
        return self.market_value - self.cost_basis