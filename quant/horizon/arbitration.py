from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math


class Horizon(str, Enum):
    INTRADAY = "INTRADAY"
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"
    MACRO = "MACRO"


@dataclass(frozen=True, slots=True)
class HorizonForecast:
    horizon: Horizon
    expected_return: float
    confidence: float
    uncertainty: float

    def __post_init__(self) -> None:
        if not math.isfinite(self.expected_return):
            raise ValueError(
                "expected_return must be finite"
            )

        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(
                "confidence must be in [0,1]"
            )

        if not 0.0 <= self.uncertainty <= 1.0:
            raise ValueError(
                "uncertainty must be in [0,1]"
            )


@dataclass(frozen=True, slots=True)
class HorizonDecision:
    expected_return: float
    confidence: float
    disagreement: float
    dominant_horizon: Horizon


class HorizonArbitrator:

    DEFAULT_WEIGHTS = {
        Horizon.INTRADAY: 0.10,
        Horizon.DAILY: 0.20,
        Horizon.WEEKLY: 0.30,
        Horizon.MONTHLY: 0.25,
        Horizon.MACRO: 0.15,
    }

    def __init__(
        self,
        weights: dict[Horizon, float] | None = None,
    ) -> None:

        self.weights = dict(
            weights
            if weights is not None
            else self.DEFAULT_WEIGHTS
        )

        if not self.weights:
            raise ValueError(
                "weights cannot be empty"
            )

        total = sum(
            self.weights.values()
        )

        if any(
            weight < 0
            for weight in self.weights.values()
        ):
            raise ValueError(
                "weights cannot be negative"
            )

        if not math.isclose(
            total,
            1.0,
            rel_tol=1e-9,
            abs_tol=1e-12,
        ):
            raise ValueError(
                "horizon weights must sum to 1"
            )

    def arbitrate(
        self,
        forecasts: list[HorizonForecast],
    ) -> HorizonDecision:

        if not forecasts:
            raise ValueError(
                "no horizon forecasts"
            )

        weighted: list[
            tuple[HorizonForecast, float]
        ] = []

        for forecast in forecasts:

            base_weight = self.weights.get(
                forecast.horizon,
                0.0,
            )

            effective_weight = (
                base_weight
                * forecast.confidence
                * (1.0 - forecast.uncertainty)
            )

            weighted.append(
                (
                    forecast,
                    effective_weight,
                )
            )

        total_weight = sum(
            weight
            for _, weight in weighted
        )

        if total_weight <= 0.0:
            return HorizonDecision(
                expected_return=0.0,
                confidence=0.0,
                disagreement=1.0,
                dominant_horizon=(
                    forecasts[0].horizon
                ),
            )

        expected_return = sum(
            forecast.expected_return * weight
            for forecast, weight
            in weighted
        ) / total_weight

        confidence = sum(
            forecast.confidence * weight
            for forecast, weight
            in weighted
        ) / total_weight

        disagreement = sum(
            weight
            * abs(
                forecast.expected_return
                - expected_return
            )
            for forecast, weight
            in weighted
        ) / total_weight

        dominant_horizon = max(
            weighted,
            key=lambda item: item[1],
        )[0].horizon

        return HorizonDecision(
            expected_return=expected_return,
            confidence=confidence,
            disagreement=disagreement,
            dominant_horizon=dominant_horizon,
        )