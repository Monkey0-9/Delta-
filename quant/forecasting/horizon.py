from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from decision.horizon import DecisionHorizon
from .forecast import Forecast


@dataclass(frozen=True, slots=True)
class HorizonForecast:
    horizon: DecisionHorizon
    forecast: Forecast
    weight: Decimal

    def __post_init__(self) -> None:
        if self.weight < Decimal("0"):
            raise ValueError("weight cannot be negative.")


class MultiHorizonAggregator:
    @staticmethod
    def aggregate(
        forecasts: tuple[HorizonForecast, ...],
    ) -> Decimal:

        if not forecasts:
            return Decimal("0")

        total_weight = sum(
            (item.weight for item in forecasts),
            Decimal("0"),
        )

        if total_weight <= Decimal("0"):
            return Decimal("0")

        weighted_return = sum(
            (
                item.forecast.expected_return
                * item.weight
                for item in forecasts
            ),
            Decimal("0"),
        )

        return weighted_return / total_weight