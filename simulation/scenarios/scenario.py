from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum


class ScenarioType(StrEnum):
    EQUITY_CRASH = "equity_crash"
    EQUITY_RALLY = "equity_rally"
    VOLATILITY_SHOCK = "volatility_shock"
    RATE_SHOCK = "rate_shock"
    YIELD_CURVE_SHIFT = "yield_curve_shift"
    FX_SHOCK = "fx_shock"
    CREDIT_SPREAD_SHOCK = "credit_spread_shock"
    LIQUIDITY_SHOCK = "liquidity_shock"
    CORRELATION_BREAK = "correlation_break"
    SECTOR_CRASH = "sector_crash"
    COMMODITY_SHOCK = "commodity_shock"
    GAP_EVENT = "gap_event"
    MACRO_SHOCK = "macro_shock"
    MULTI_FACTOR = "multi_factor"
    CUSTOM = "custom"


@dataclass(frozen=True, slots=True)
class ScenarioFactor:
    name: str
    shock: Decimal
    unit: str = "relative"

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("Scenario factor name cannot be empty.")


@dataclass(frozen=True, slots=True)
class StressScenario:
    scenario_id: str
    scenario_type: ScenarioType
    name: str
    factors: tuple[ScenarioFactor, ...]
    severity: Decimal
    seed: int = 0

    def __post_init__(self) -> None:
        if not self.scenario_id.strip():
            raise ValueError("scenario_id cannot be empty.")

        if not self.name.strip():
            raise ValueError("Scenario name cannot be empty.")

        if not Decimal("0") <= self.severity <= Decimal("1"):
            raise ValueError("severity must be between 0 and 1.")

        if not self.factors:
            raise ValueError("Scenario must contain at least one factor.")