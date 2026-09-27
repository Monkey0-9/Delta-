from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from decimal import Decimal


class Regime(StrEnum):
    NORMAL = "normal"
    TRENDING = "trending"
    HIGH_VOLATILITY = "high_volatility"
    CRISIS = "crisis"
    ILLIQUID = "illiquid"


@dataclass(frozen=True, slots=True)
class RegimeProbability:
    regime: Regime
    probability: Decimal

    def __post_init__(self) -> None:
        if not Decimal("0") <= self.probability <= Decimal("1"):
            raise ValueError(
                "Regime probability must be between 0 and 1."
            )


@dataclass(frozen=True, slots=True)
class RegimeState:
    probabilities: tuple[RegimeProbability, ...]

    def __post_init__(self) -> None:
        total = sum(
            item.probability
            for item in self.probabilities
        )

        if abs(total - Decimal("1")) > Decimal("0.000001"):
            raise ValueError(
                "Regime probabilities must sum to 1."
            )

    @property
    def dominant(self) -> Regime:
        return max(
            self.probabilities,
            key=lambda item: item.probability,
        ).regime