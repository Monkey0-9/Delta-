from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID, uuid4

from .timestamp import ensure_utc, utc_now


class OrderSide(StrEnum):
    BUY = "buy"
    SELL = "sell"


class OrderType(StrEnum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


class TimeInForce(StrEnum):
    DAY = "day"
    GTC = "gtc"
    IOC = "ioc"
    FOK = "fok"


class OrderStatus(StrEnum):
    CREATED = "created"
    VALIDATED = "validated"
    RISK_APPROVED = "risk_approved"
    SUBMITTED = "submitted"
    ACKNOWLEDGED = "acknowledged"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCEL_PENDING = "cancel_pending"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"
    FAILED = "failed"


_TERMINAL_STATUSES = frozenset(
    {
        OrderStatus.FILLED,
        OrderStatus.CANCELLED,
        OrderStatus.REJECTED,
        OrderStatus.EXPIRED,
        OrderStatus.FAILED,
    }
)


_ALLOWED_TRANSITIONS: dict[
    OrderStatus,
    frozenset[OrderStatus],
] = {
    OrderStatus.CREATED: frozenset(
        {OrderStatus.VALIDATED, OrderStatus.REJECTED}
    ),
    OrderStatus.VALIDATED: frozenset(
        {OrderStatus.RISK_APPROVED, OrderStatus.REJECTED}
    ),
    OrderStatus.RISK_APPROVED: frozenset(
        {OrderStatus.SUBMITTED, OrderStatus.REJECTED}
    ),
    OrderStatus.SUBMITTED: frozenset(
        {
            OrderStatus.ACKNOWLEDGED,
            OrderStatus.REJECTED,
            OrderStatus.FAILED,
        }
    ),
    OrderStatus.ACKNOWLEDGED: frozenset(
        {
            OrderStatus.PARTIALLY_FILLED,
            OrderStatus.FILLED,
            OrderStatus.CANCEL_PENDING,
            OrderStatus.EXPIRED,
            OrderStatus.FAILED,
        }
    ),
    OrderStatus.PARTIALLY_FILLED: frozenset(
        {
            OrderStatus.PARTIALLY_FILLED,
            OrderStatus.FILLED,
            OrderStatus.CANCEL_PENDING,
            OrderStatus.EXPIRED,
            OrderStatus.FAILED,
        }
    ),
    OrderStatus.CANCEL_PENDING: frozenset(
        {
            OrderStatus.CANCELLED,
            OrderStatus.FILLED,
            OrderStatus.FAILED,
        }
    ),
    OrderStatus.FILLED: frozenset(),
    OrderStatus.CANCELLED: frozenset(),
    OrderStatus.REJECTED: frozenset(),
    OrderStatus.EXPIRED: frozenset(),
    OrderStatus.FAILED: frozenset(),
}


@dataclass(frozen=True, slots=True)
class Order:
    """
    Immutable order and lifecycle state.

    The order object is a domain contract. Execution engines,
    risk controls and broker adapters must not mutate it in place.
    """

    instrument_id: UUID
    side: OrderSide
    quantity: Decimal

    order_type: OrderType = OrderType.MARKET
    time_in_force: TimeInForce = TimeInForce.DAY

    limit_price: Decimal | None = None
    stop_price: Decimal | None = None

    order_id: UUID = field(default_factory=uuid4)
    idempotency_key: str = field(
        default_factory=lambda: str(uuid4())
    )

    status: OrderStatus = OrderStatus.CREATED
    filled_quantity: Decimal = Decimal("0")

    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        if self.quantity <= Decimal("0"):
            raise ValueError(
                "Order quantity must be positive."
            )

        if self.filled_quantity < Decimal("0"):
            raise ValueError(
                "Filled quantity cannot be negative."
            )

        if self.filled_quantity > self.quantity:
            raise ValueError(
                "Filled quantity cannot exceed order quantity."
            )

        if not self.idempotency_key.strip():
            raise ValueError(
                "Idempotency key cannot be empty."
            )

        if self.order_type in {
            OrderType.LIMIT,
            OrderType.STOP_LIMIT,
        }:
            if self.limit_price is None:
                raise ValueError(
                    "Limit orders require limit_price."
                )

            if self.limit_price <= Decimal("0"):
                raise ValueError(
                    "Limit price must be positive."
                )

        if self.order_type in {
            OrderType.STOP,
            OrderType.STOP_LIMIT,
        }:
            if self.stop_price is None:
                raise ValueError(
                    "Stop orders require stop_price."
                )

            if self.stop_price <= Decimal("0"):
                raise ValueError(
                    "Stop price must be positive."
                )

        object.__setattr__(
            self,
            "created_at",
            ensure_utc(self.created_at),
        )

        object.__setattr__(
            self,
            "updated_at",
            ensure_utc(self.updated_at),
        )

    @property
    def remaining_quantity(self) -> Decimal:
        return self.quantity - self.filled_quantity

    @property
    def is_terminal(self) -> bool:
        return self.status in _TERMINAL_STATUSES

    @property
    def is_filled(self) -> bool:
        return self.filled_quantity == self.quantity

    def transition(
        self,
        new_status: OrderStatus,
        *,
        timestamp: datetime | None = None,
    ) -> Order:
        if new_status not in _ALLOWED_TRANSITIONS[self.status]:
            raise ValueError(
                f"Invalid order transition: "
                f"{self.status.value} -> {new_status.value}"
            )

        return self._replace(
            status=new_status,
            updated_at=timestamp or utc_now(),
        )

    def record_fill(
        self,
        quantity: Decimal,
        *,
        timestamp: datetime | None = None,
    ) -> Order:
        if quantity <= Decimal("0"):
            raise ValueError(
                "Fill quantity must be positive."
            )

        if self.is_terminal:
            raise ValueError(
                "Cannot fill a terminal order."
            )

        if quantity > self.remaining_quantity:
            raise ValueError(
                "Fill exceeds remaining order quantity."
            )

        new_filled_quantity = (
            self.filled_quantity + quantity
        )

        new_status = (
            OrderStatus.FILLED
            if new_filled_quantity == self.quantity
            else OrderStatus.PARTIALLY_FILLED
        )

        if new_status not in _ALLOWED_TRANSITIONS[self.status]:
            raise ValueError(
                f"Invalid fill transition: "
                f"{self.status.value} -> {new_status.value}"
            )

        return self._replace(
            status=new_status,
            filled_quantity=new_filled_quantity,
            updated_at=timestamp or utc_now(),
        )

    def _replace(
        self,
        *,
        status: OrderStatus,
        filled_quantity: Decimal | None = None,
        updated_at: datetime,
    ) -> Order:
        return Order(
            instrument_id=self.instrument_id,
            side=self.side,
            quantity=self.quantity,
            order_type=self.order_type,
            time_in_force=self.time_in_force,
            limit_price=self.limit_price,
            stop_price=self.stop_price,
            order_id=self.order_id,
            idempotency_key=self.idempotency_key,
            status=status,
            filled_quantity=(
                self.filled_quantity
                if filled_quantity is None
                else filled_quantity
            ),
            created_at=self.created_at,
            updated_at=updated_at,
        )


# Backwards-compatible public name used by the original
# domain API. There is still exactly one canonical order model.
OrderIntent = Order