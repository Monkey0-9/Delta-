from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class CounterfactualAction:
    name: str
    expected_return: Decimal
    expected_risk: Decimal

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("action name cannot be empty.")

        if self.expected_risk < Decimal("0"):
            raise ValueError(
                "expected_risk cannot be negative."
            )


@dataclass(frozen=True, slots=True)
class CounterfactualResult:
    baseline: CounterfactualAction
    alternatives: tuple[CounterfactualAction, ...]

    @staticmethod
    def _score(action: CounterfactualAction) -> Decimal:
        """
        Contract-level risk-adjusted score.

        Expected return remains the primary signal while risk
        acts as a bounded penalty. This is intentionally simple;
        production portfolio optimization belongs in quant/portfolio.
        """
        risk_penalty = action.expected_risk * Decimal("0.25")
        return action.expected_return - risk_penalty

    @property
    def best_risk_adjusted_alternative(
        self,
    ) -> CounterfactualAction:
        candidates = (
            self.baseline,
            *self.alternatives,
        )

        return max(
            candidates,
            key=self._score,
        )