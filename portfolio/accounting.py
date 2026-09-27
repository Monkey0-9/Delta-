from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class PnL:
    realized: Decimal = Decimal("0")
    unrealized: Decimal = Decimal("0")

    @property
    def total(self) -> Decimal:
        return self.realized + self.unrealized


class PortfolioAccounting:
    @staticmethod
    def unrealized(
        quantity: Decimal,
        average_cost: Decimal,
        market_price: Decimal,
    ) -> Decimal:
        if quantity < Decimal("0"):
            raise ValueError("Quantity cannot be negative.")

        if average_cost < Decimal("0"):
            raise ValueError("Average cost cannot be negative.")

        if market_price < Decimal("0"):
            raise ValueError("Market price cannot be negative.")

        return quantity * (market_price - average_cost)

    @staticmethod
    def realized_sell_pnl(
        quantity: Decimal,
        average_cost: Decimal,
        execution_price: Decimal,
    ) -> Decimal:
        if quantity <= Decimal("0"):
            raise ValueError("Sell quantity must be positive.")

        if average_cost < Decimal("0"):
            raise ValueError("Average cost cannot be negative.")

        if execution_price < Decimal("0"):
            raise ValueError("Execution price cannot be negative.")

        return quantity * (execution_price - average_cost)