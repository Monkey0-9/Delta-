from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum


class ForecastDirection(StrEnum):
    UP = "up"
    DOWN = "down"
    FLAT = "flat"


@dataclass(frozen=True, slots=True)
class Forecast:
    symbol: str
    horizon: str
    expected_return: Decimal
    confidence: Decimal
    direction: ForecastDirection
    model_version: str

    def __post_init__(self) -> None:
        if not self.symbol.strip():
            raise ValueError("symbol cannot be empty.")

        if not Decimal("0") <= self.confidence <= Decimal("1"):
            raise ValueError(
                "confidence must be between 0 and 1."
            )

        if not self.model_version:
            raise ValueError(
                "model_version cannot be empty."
            )