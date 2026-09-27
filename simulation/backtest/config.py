from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class BacktestConfig:
    initial_cash: Decimal
    commission_rate: Decimal = Decimal("0")
    slippage_bps: Decimal = Decimal("0")
    allow_short: bool = False

    def __post_init__(self) -> None:
        if self.initial_cash <= Decimal("0"):
            raise ValueError(
                "Initial cash must be positive."
            )

        if self.commission_rate < Decimal("0"):
            raise ValueError(
                "Commission rate cannot be negative."
            )

        if self.slippage_bps < Decimal("0"):
            raise ValueError(
                "Slippage cannot be negative."
            )
