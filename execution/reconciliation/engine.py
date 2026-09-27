from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping


class ReconciliationStatus(str, Enum):
    MATCHED = "MATCHED"
    MISSING_ORDER = "MISSING_ORDER"
    MISSING_FILL = "MISSING_FILL"
    QUANTITY_MISMATCH = "QUANTITY_MISMATCH"
    PRICE_MISMATCH = "PRICE_MISMATCH"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class InternalOrder:
    order_id: str
    asset: str
    quantity: float


@dataclass(frozen=True, slots=True)
class ExternalFill:
    order_id: str
    asset: str
    quantity: float
    price: float


@dataclass(frozen=True, slots=True)
class ReconciliationResult:
    order_id: str
    status: ReconciliationStatus
    expected_quantity: float
    actual_quantity: float
    message: str


class ReconciliationEngine:

    def reconcile(
        self,
        orders: Mapping[str, InternalOrder],
        fills: Mapping[str, ExternalFill],
    ) -> tuple[ReconciliationResult, ...]:

        order_ids = (
            set(orders)
            | set(fills)
        )

        results = []

        for order_id in sorted(order_ids):

            order = orders.get(order_id)
            fill = fills.get(order_id)

            if order is None:
                results.append(
                    ReconciliationResult(
                        order_id,
                        ReconciliationStatus.MISSING_ORDER,
                        0.0,
                        fill.quantity if fill else 0.0,
                        "external fill has no internal order",
                    )
                )
                continue

            if fill is None:
                results.append(
                    ReconciliationResult(
                        order_id,
                        ReconciliationStatus.MISSING_FILL,
                        order.quantity,
                        0.0,
                        "internal order has no external fill",
                    )
                )
                continue

            if order.asset != fill.asset:
                results.append(
                    ReconciliationResult(
                        order_id,
                        ReconciliationStatus.UNKNOWN,
                        order.quantity,
                        fill.quantity,
                        "asset mismatch",
                    )
                )
                continue

            if order.quantity != fill.quantity:
                results.append(
                    ReconciliationResult(
                        order_id,
                        ReconciliationStatus.QUANTITY_MISMATCH,
                        order.quantity,
                        fill.quantity,
                        "quantity mismatch",
                    )
                )
                continue

            results.append(
                ReconciliationResult(
                    order_id,
                    ReconciliationStatus.MATCHED,
                    order.quantity,
                    fill.quantity,
                    "matched",
                )
            )

        return tuple(results)