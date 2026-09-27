from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class SimulatorConfig:
    commission_rate: Decimal = Decimal("0")
    slippage_bps: Decimal = Decimal("0")
    max_participation_rate: Decimal = Decimal("1")

    def __post_init__(self) -> None:
        if self.commission_rate < Decimal("0"):
            raise ValueError(
                "Commission rate cannot be negative."
            )

        if self.slippage_bps < Decimal("0"):
            raise ValueError(
                "Slippage cannot be negative."
            )

        if not (
            Decimal("0")
            < self.max_participation_rate
            <= Decimal("1")
        ):
            raise ValueError(
                "Participation rate must be in (0, 1]."
            )