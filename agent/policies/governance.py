from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class AutonomousGateInput:
    data_freshness_seconds: Decimal
    maximum_data_age_seconds: Decimal

    uncertainty: Decimal
    maximum_uncertainty: Decimal

    risk_approved: bool
    authorization_approved: bool
    kill_switch_active: bool


@dataclass(frozen=True, slots=True)
class AutonomousDecision:
    allowed: bool
    reason: str


class AutonomousGate:

    def evaluate(
        self,
        value: AutonomousGateInput,
    ) -> AutonomousDecision:

        if value.kill_switch_active:
            return AutonomousDecision(
                False,
                "Kill switch is active.",
            )

        if not value.risk_approved:
            return AutonomousDecision(
                False,
                "Risk approval missing.",
            )

        if not value.authorization_approved:
            return AutonomousDecision(
                False,
                "Authorization missing.",
            )

        if (
            value.data_freshness_seconds
            > value.maximum_data_age_seconds
        ):
            return AutonomousDecision(
                False,
                "Market data is stale.",
            )

        if value.uncertainty > value.maximum_uncertainty:
            return AutonomousDecision(
                False,
                "Uncertainty exceeds autonomous threshold.",
            )

        return AutonomousDecision(
            True,
            "Autonomous execution gate passed.",
        )