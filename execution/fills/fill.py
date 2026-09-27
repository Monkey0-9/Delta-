from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from core.domain.timestamp import ensure_utc, utc_now


@dataclass(frozen=True, slots=True)
class Fill:
    order_id: UUID
    instrument_id: UUID
    quantity: Decimal
    price: Decimal

    fee: Decimal = Decimal("0")
    slippage: Decimal = Decimal("0")

    fill_id: UUID = field(default_factory=uuid4)
    executed_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        if self.quantity <= Decimal("0"):
            raise ValueError("Fill quantity must be positive.")

        if self.price <= Decimal("0"):
            raise ValueError("Fill price must be positive.")

        if self.fee < Decimal("0"):
            raise ValueError("Fee cannot be negative.")

        if self.slippage < Decimal("0"):
            raise ValueError("Slippage cannot be negative.")

        object.__setattr__(
            self,
            "executed_at",
            ensure_utc(self.executed_at),
        )

    @property
    def notional(self) -> Decimal:
        return self.quantity * self.price

    @property
    def total_cost(self) -> Decimal:
        return self.notional + self.fee