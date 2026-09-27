from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class OrderState(str, Enum):

    CREATED = "CREATED"
    VALIDATED = "VALIDATED"
    RISK_APPROVED = "RISK_APPROVED"
    AUTHORIZED = "AUTHORIZED"
    SUBMITTED = "SUBMITTED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"

    REJECTED = "REJECTED"
    CANCEL_PENDING = "CANCEL_PENDING"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"


TRANSITIONS = {

    OrderState.CREATED: {
        OrderState.VALIDATED,
        OrderState.REJECTED,
    },

    OrderState.VALIDATED: {
        OrderState.RISK_APPROVED,
        OrderState.REJECTED,
    },

    OrderState.RISK_APPROVED: {
        OrderState.AUTHORIZED,
        OrderState.REJECTED,
    },

    OrderState.AUTHORIZED: {
        OrderState.SUBMITTED,
        OrderState.REJECTED,
    },

    OrderState.SUBMITTED: {
        OrderState.ACKNOWLEDGED,
        OrderState.FAILED,
        OrderState.UNKNOWN,
    },

    OrderState.ACKNOWLEDGED: {
        OrderState.PARTIALLY_FILLED,
        OrderState.FILLED,
        OrderState.CANCEL_PENDING,
        OrderState.EXPIRED,
    },

    OrderState.PARTIALLY_FILLED: {
        OrderState.PARTIALLY_FILLED,
        OrderState.FILLED,
        OrderState.CANCEL_PENDING,
    },

    OrderState.CANCEL_PENDING: {
        OrderState.CANCELLED,
        OrderState.PARTIALLY_FILLED,
        OrderState.FILLED,
        OrderState.UNKNOWN,
    },

    OrderState.FILLED: set(),
    OrderState.REJECTED: set(),
    OrderState.CANCELLED: set(),
    OrderState.EXPIRED: set(),
    OrderState.FAILED: set(),
    OrderState.UNKNOWN: {
        OrderState.ACKNOWLEDGED,
        OrderState.FILLED,
        OrderState.CANCELLED,
        OrderState.FAILED,
    },
}


@dataclass(frozen=True, slots=True)
class Order:

    order_id: str
    idempotency_key: str
    asset: str
    quantity: float
    state: OrderState


class OMS:

    def __init__(self):

        self.orders: dict[
            str,
            Order,
        ] = {}

    def create(
        self,
        *,
        order_id: str,
        idempotency_key: str,
        asset: str,
        quantity: float,
    ) -> Order:

        if not order_id:
            raise ValueError(
                "order_id required"
            )

        if not idempotency_key:
            raise ValueError(
                "idempotency_key required"
            )

        if quantity <= 0:
            raise ValueError(
                "quantity must be positive"
            )

        if any(
            order.idempotency_key
            == idempotency_key
            for order
            in self.orders.values()
        ):
            raise ValueError(
                "duplicate idempotency key"
            )

        order = Order(
            order_id,
            idempotency_key,
            asset,
            quantity,
            OrderState.CREATED,
        )

        self.orders[
            order_id
        ] = order

        return order

    def transition(
        self,
        order_id: str,
        target: OrderState,
    ) -> Order:

        current = self.orders[
            order_id
        ]

        allowed = TRANSITIONS[
            current.state
        ]

        if target not in allowed:
            raise ValueError(
                f"illegal transition "
                f"{current.state} -> {target}"
            )

        updated = Order(
            current.order_id,
            current.idempotency_key,
            current.asset,
            current.quantity,
            target,
        )

        self.orders[
            order_id
        ] = updated

        return updated