from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Horizon(StrEnum):
    INTRADAY = "intraday"
    SHORT_TERM = "short_term"
    MEDIUM_TERM = "medium_term"
    LONG_TERM = "long_term"


class UncertaintyType(StrEnum):
    DATA = "data"
    MODEL = "model"
    REGIME = "regime"
    EXECUTION = "execution"


class DecisionAction(StrEnum):
    TRADE = "trade"
    WAIT = "wait"
    NO_TRADE = "no_trade"
    INVESTIGATE = "investigate"


@dataclass(frozen=True, slots=True)
class HorizonForecast:
    horizon: Horizon

    expected_return: float
    volatility: float

    confidence: float

    data_uncertainty: float
    model_uncertainty: float
    regime_uncertainty: float
    execution_uncertainty: float

    def validate(self) -> None:

        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(
                "confidence must be in [0,1]"
            )

        uncertainty = (
            self.data_uncertainty,
            self.model_uncertainty,
            self.regime_uncertainty,
            self.execution_uncertainty,
        )

        if any(value < 0.0 for value in uncertainty):
            raise ValueError(
                "uncertainty values cannot be negative"
            )