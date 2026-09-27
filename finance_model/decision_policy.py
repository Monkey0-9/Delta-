from __future__ import annotations

from dataclasses import dataclass

from .uncertainty import (
    DecisionAction,
    HorizonForecast,
)


@dataclass(frozen=True, slots=True)
class DecisionPolicy:

    minimum_confidence: float = 0.70
    maximum_total_uncertainty: float = 0.60

    def decide(
        self,
        forecast: HorizonForecast,
    ) -> DecisionAction:

        forecast.validate()

        total_uncertainty = (
            forecast.data_uncertainty
            + forecast.model_uncertainty
            + forecast.regime_uncertainty
            + forecast.execution_uncertainty
        )

        if forecast.confidence < self.minimum_confidence:
            return DecisionAction.INVESTIGATE

        if total_uncertainty > self.maximum_total_uncertainty:
            return DecisionAction.NO_TRADE

        if forecast.expected_return > 0:
            return DecisionAction.TRADE

        return DecisionAction.WAIT