from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class RiskStatus(str, Enum):
    APPROVED = "APPROVED"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True, slots=True)
class RiskDecision:

    decision_id: str
    status: RiskStatus
    approved_quantity: float
    reason: str
    limits_version: str


class RiskFirewall:

    def __init__(
        self,
        max_quantity: float,
        max_gross: float,
    ):
        if max_quantity <= 0:
            raise ValueError(
                "max_quantity must be positive"
            )

        if max_gross <= 0:
            raise ValueError(
                "max_gross must be positive"
            )

        self.max_quantity = max_quantity
        self.max_gross = max_gross

    def evaluate(
        self,
        *,
        decision_id: str,
        requested_quantity: float,
        current_gross: float,
        limits_version: str,
    ) -> RiskDecision:

        if requested_quantity <= 0:
            return RiskDecision(
                decision_id,
                RiskStatus.BLOCKED,
                0.0,
                "invalid quantity",
                limits_version,
            )

        if current_gross >= self.max_gross:
            return RiskDecision(
                decision_id,
                RiskStatus.BLOCKED,
                0.0,
                "gross exposure limit",
                limits_version,
            )

        available = (
            self.max_gross
            - current_gross
        )

        approved = min(
            requested_quantity,
            self.max_quantity,
            available,
        )

        if approved <= 0:
            return RiskDecision(
                decision_id,
                RiskStatus.BLOCKED,
                0.0,
                "no risk capacity",
                limits_version,
            )

        return RiskDecision(
            decision_id,
            RiskStatus.APPROVED,
            approved,
            "risk checks passed",
            limits_version,
        )