from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from .decision import (
    Decision,
    DecisionAction,
    DecisionEvidence,
)
from .horizon import DecisionHorizon


@dataclass(frozen=True, slots=True)
class DecisionInput:
    """
    Validated input supplied to the decision engine.

    Utility model: U = expected_return - risk_penalty - transaction_cost.
    BUY/SELL fire only when utility clears `utility_threshold`; otherwise
    WAIT. Sign-only trading without cost/risk terms is rejected by
    requiring explicit (possibly zero, explicitly stated) terms.
    """

    instrument_id: UUID
    horizon: DecisionHorizon
    expected_return: Decimal
    confidence: Decimal

    evidence: tuple[DecisionEvidence, ...] = ()

    risk_penalty: Decimal = Decimal("0")
    transaction_cost: Decimal = Decimal("0")
    utility_threshold: Decimal = Decimal("0")

    model_version: str = "unknown"
    world_state_version: str = "unknown"

    def __post_init__(self) -> None:
        if not Decimal("0") <= self.confidence <= Decimal("1"):
            raise ValueError(
                "Confidence must be between 0 and 1."
            )

        if not self.model_version:
            raise ValueError(
                "model_version cannot be empty."
            )

        if not self.world_state_version:
            raise ValueError(
                "world_state_version cannot be empty."
            )


class DecisionEngine:
    """
    Converts validated quantitative/research signals
    into a structured Decision.

    The engine does NOT:
        - place orders
        - contact brokers
        - bypass risk controls
        - modify portfolio state
    """

    def evaluate(
        self,
        data: DecisionInput,
    ) -> Decision:

        action = self._classify(
            expected_return=data.expected_return,
            confidence=data.confidence,
            risk_penalty=data.risk_penalty,
            transaction_cost=data.transaction_cost,
            utility_threshold=data.utility_threshold,
        )

        return Decision(
            instrument_id=data.instrument_id,
            action=action,
            horizon=data.horizon,
            confidence=data.confidence,
            expected_return=data.expected_return,
            evidence=data.evidence,
            model_version=data.model_version,
            world_state_version=data.world_state_version,
        )

    @staticmethod
    def _classify(
        expected_return: Decimal,
        confidence: Decimal,
        risk_penalty: Decimal = Decimal("0"),
        transaction_cost: Decimal = Decimal("0"),
        utility_threshold: Decimal = Decimal("0"),
    ) -> DecisionAction:
        """Utility-gated classification: U = ER - risk - cost.

        WAIT unless confidence is sufficient AND net utility clears the
        threshold. Direction follows the sign of net utility, not gross
        expected return.
        """
        if confidence < Decimal("0.50"):
            return DecisionAction.WAIT

        long_utility = expected_return - risk_penalty - transaction_cost
        short_utility = -expected_return - risk_penalty - transaction_cost

        if long_utility > utility_threshold:
            return DecisionAction.BUY
        if short_utility > utility_threshold:
            return DecisionAction.SELL

        return DecisionAction.WAIT