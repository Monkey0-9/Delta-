from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from execution.fills.fill import Fill


class ReconciliationError(RuntimeError):
    pass


class ExecutionReconciler:

    @staticmethod
    def check_unknown_order(order_id: UUID, known: set[UUID]) -> None:
        if order_id not in known:
            raise ReconciliationError("Unknown order on reconciliation: incident raised.")

    @staticmethod
    def validate_fill(
        *,
        order_id: UUID,
        expected_quantity: Decimal,
        already_filled: Decimal,
        fill: Fill,
    ) -> None:
        if fill.order_id != order_id:
            raise ReconciliationError(
                "Fill belongs to a different order."
            )

        if fill.quantity <= Decimal("0"):
            raise ReconciliationError(
                "Fill quantity must be positive."
            )

        total_filled = already_filled + fill.quantity

        if total_filled > expected_quantity:
            raise ReconciliationError(
                "Fill exceeds remaining order quantity."
            )