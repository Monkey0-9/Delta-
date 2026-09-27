from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class BacktestConfig:
    initial_cash: Decimal
    commission_rate: Decimal = Decimal("0.0005")  # 5 bps per dollar traded (institutional baseline)
    slippage_bps: Decimal = Decimal("5.0")  # 5 bps baseline spread/impact
    borrow_fee_annual_pct: Decimal = Decimal("1.5")  # 150 bps hard-to-borrow financing
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

        if self.borrow_fee_annual_pct < Decimal("0"):
            raise ValueError(
                "Borrow fee percentage cannot be negative."
            )
