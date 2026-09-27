from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Opportunity:
    symbol: str
    direction: str
    horizon: str
    expected_return: float
    predicted_risk: float
    confidence: float
    regime: str
    estimated_cost: float
    risk_status: str
    decision: str


def qualifies(
    opportunity: Opportunity,
    minimum_confidence: float,
) -> bool:

    if opportunity.confidence < minimum_confidence:
        return False

    if opportunity.risk_status != "APPROVED":
        return False

    if opportunity.decision != "TRADE":
        return False

    return True