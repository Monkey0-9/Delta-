from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from core.domain.order import Order, OrderStatus
from core.domain.timestamp import utc_now


@dataclass(slots=True)
class ManagedOrder:
    order_id: UUID
    instrument_id: UUID
    side: str
    quantity: Decimal
    status: OrderStatus = OrderStatus.CREATED
    filled_qty: Decimal = Decimal("0")
    idempotency_key: str = ""
    updated_at: datetime = field(default_factory=utc_now)

    def advance(self, nxt: OrderStatus) -> None:
        tmp = Order(
            instrument_id=self.instrument_id,
            side=self.side,  # type: ignore[arg-type]
            quantity=self.quantity,
            order_id=self.order_id,
            idempotency_key=self.idempotency_key or "k",
            status=self.status,
            filled_quantity=self.filled_qty,
        ).transition(nxt)
        self.status = tmp.status
        self.updated_at = utc_now()

    def apply_fill(self, qty: Decimal) -> None:
        if qty <= 0:
            raise ValueError("fill qty must be positive.")
        if self.filled_qty + qty > self.quantity:
            raise ValueError("overfill.")
        self.filled_qty += qty
        if self.filled_qty == self.quantity:
            self.advance(OrderStatus.FILLED)
        else:
            self.advance(OrderStatus.PARTIALLY_FILLED)
