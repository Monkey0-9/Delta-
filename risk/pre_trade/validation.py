from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from uuid import UUID


class RiskVerdict(StrEnum):
    APPROVE = "approve"
    REDUCE = "reduce"
    BLOCK = "block"


@dataclass(frozen=True, slots=True)
class TradeIntent:
    order_id: UUID
    instrument_id: UUID
    side: str  # buy/sell
    quantity: Decimal
    limit_price: Decimal | None = None
    idempotency_key: str = ""
    authorized: bool = False


@dataclass(frozen=True, slots=True)
class RiskDecision:
    risk_decision_id: str
    decision_id: str
    limits_version: str
    verdict: RiskVerdict
    reasons: tuple[str, ...] = ()


def validate_intent(intent: TradeIntent) -> list[str]:
    errors: list[str] = []
    if intent.quantity <= 0:
        errors.append("quantity must be positive")
    if intent.limit_price is not None and intent.limit_price <= 0:
        errors.append("limit price must be positive")
    if not intent.idempotency_key:
        errors.append("idempotency_key required")
    if not intent.authorized:
        errors.append("missing authorization")
    return errors
