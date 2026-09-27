from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class StressResult:
    scenario_id: str

    portfolio_pnl: Decimal
    portfolio_return: Decimal
    max_drawdown: Decimal

    gross_exposure_before: Decimal
    gross_exposure_after: Decimal

    net_exposure_before: Decimal
    net_exposure_after: Decimal

    leverage_before: Decimal
    leverage_after: Decimal

    liquidity_impact: Decimal
    margin_impact: Decimal

    affected_positions: tuple[str, ...]
    risk_limit_breaches: tuple[str, ...]

    confidence: Decimal

    @property
    def breached(self) -> bool:
        return bool(self.risk_limit_breaches)

    def __post_init__(self) -> None:
        if not self.scenario_id:
            raise ValueError("scenario_id cannot be empty.")

        if not Decimal("0") <= self.confidence <= Decimal("1"):
            raise ValueError("confidence must be between 0 and 1.")

        if self.max_drawdown > Decimal("0"):
            raise ValueError("max_drawdown must be <= 0.")