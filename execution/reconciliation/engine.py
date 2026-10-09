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
    ASSET_MISMATCH = "ASSET_MISMATCH"
    LEDGER_MISMATCH = "LEDGER_MISMATCH"
    UNKNOWN = "UNKNOWN"


#: Action recommendation surfaced to the caller. The engine never halts
#: anything itself — the halt decision stays with the caller.
#: Kept as module constants (not an Enum) for backward compatibility:
#: callers compare ``result.action == "HALT"`` as plain strings.
ACTION_NONE = "NONE"
ACTION_HALT = "HALT"


@dataclass(frozen=True, slots=True)
class InternalOrder:
    order_id: str
    asset: str
    quantity: float
    price: float | None = None


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
    action: str = ACTION_NONE


def _price_diverged(expected: float | None, actual: float, tolerance: float) -> bool:
    """Relative price divergence beyond tolerance. Unknown expected -> no check.

    Zero expected matches only zero actual (any nonzero fill against a
    zero-price order is a mismatch); tolerance is clamped >= 0 by the
    caller so a negative tolerance can never invert the verdict.
    """
    if expected is None:
        return False
    if expected == 0:
        return actual != 0
    return abs(actual - expected) / abs(expected) > tolerance


class ReconciliationEngine:

    def reconcile(
        self,
        orders: Mapping[str, InternalOrder],
        fills: Mapping[str, ExternalFill],
        *,
        ledger: Mapping[str, InternalOrder] | None = None,
        price_tolerance: float = 0.0,
    ) -> tuple[ReconciliationResult, ...]:
        """Two-leg (order vs fill) plus optional third-leg (ledger) compare.

        Quantity policy is EXACT float equality by design (no epsilon):
        share/contract quantities are discrete, so any difference is a
        real mismatch, not float noise. Price uses a relative tolerance
        (``price_tolerance`` clamped to >= 0); a ``None`` expected price
        skips the price leg, and the ledger price leg applies only when
        both the order and the ledger leg carry a price.

        Every non-MATCHED result carries ``action="HALT"`` as an explicit
        recommendation with a reason in ``message``; the caller owns the
        halt decision (no kill wiring here).
        """
        tolerance = max(float(price_tolerance), 0.0)
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
                        ACTION_HALT,
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
                        ACTION_HALT,
                    )
                )
                continue

            if order.asset != fill.asset:
                results.append(
                    ReconciliationResult(
                        order_id,
                        ReconciliationStatus.ASSET_MISMATCH,
                        order.quantity,
                        fill.quantity,
                        f"asset mismatch: order {order.asset} vs fill {fill.asset}",
                        ACTION_HALT,
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
                        ACTION_HALT,
                    )
                )
                continue

            if _price_diverged(order.price, fill.price, tolerance):
                results.append(
                    ReconciliationResult(
                        order_id,
                        ReconciliationStatus.PRICE_MISMATCH,
                        order.quantity,
                        fill.quantity,
                        f"price mismatch: expected {order.price} vs fill "
                        f"{fill.price} beyond tolerance {tolerance}",
                        ACTION_HALT,
                    )
                )
                continue

            if ledger is not None:
                leg = ledger.get(order_id)
                if leg is None:
                    results.append(
                        ReconciliationResult(
                            order_id,
                            ReconciliationStatus.LEDGER_MISMATCH,
                            order.quantity,
                            fill.quantity,
                            "ledger leg missing order",
                            ACTION_HALT,
                        )
                    )
                    continue
                if leg.asset != order.asset or leg.quantity != order.quantity:
                    results.append(
                        ReconciliationResult(
                            order_id,
                            ReconciliationStatus.LEDGER_MISMATCH,
                            order.quantity,
                            leg.quantity,
                            f"ledger mismatch: ledger ({leg.asset}, "
                            f"{leg.quantity}) vs order ({order.asset}, "
                            f"{order.quantity})",
                            ACTION_HALT,
                        )
                    )
                    continue
                if (
                    leg.price is not None
                    and order.price is not None
                    and _price_diverged(order.price, leg.price, tolerance)
                ):
                    results.append(
                        ReconciliationResult(
                            order_id,
                            ReconciliationStatus.LEDGER_MISMATCH,
                            order.quantity,
                            leg.quantity,
                            f"ledger price mismatch: ledger {leg.price} vs "
                            f"order {order.price} beyond tolerance {tolerance}",
                            ACTION_HALT,
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
                    ACTION_NONE,
                )
            )

        return tuple(results)