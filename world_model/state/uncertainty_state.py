from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class UncertaintyState:
    model: Decimal
    data: Decimal
    regime: Decimal
    execution: Decimal

    def __post_init__(self) -> None:
        values = (
            self.model,
            self.data,
            self.regime,
            self.execution,
        )

        if any(
            not Decimal("0") <= value <= Decimal("1")
            for value in values
        ):
            raise ValueError(
                "uncertainty values must be between 0 and 1."
            )

    @property
    def aggregate(self) -> Decimal:
        return (
            self.model
            + self.data
            + self.regime
            + self.execution
        ) / Decimal("4")