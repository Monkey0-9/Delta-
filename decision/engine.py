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
    """

    instrument_id: UUID
    horizon: DecisionHorizon
    expected_return: Decimal
    confidence: Decimal

    evidence: tuple[DecisionEvidence, ...] = ()

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
    ) -> DecisionAction:

        if confidence < Decimal("0.50"):
            return DecisionAction.WAIT

        if expected_return > Decimal("0"):
            return DecisionAction.BUY

        if expected_return < Decimal("0"):
            return DecisionAction.SELL

        return DecisionAction.HOLD