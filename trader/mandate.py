from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum


class AutonomyMode(str, Enum):
    RECOMMENDATION = "RECOMMENDATION"
    PAPER = "PAPER"
    COPILOT = "COPILOT"
    SUPERVISED = "SUPERVISED"
    AUTONOMOUS = "AUTONOMOUS"


class ExecutionMode(str, Enum):
    RECOMMENDATION = "RECOMMENDATION"
    PAPER = "PAPER"
    COPILOT = "COPILOT"
    SUPERVISED = "SUPERVISED"
    AUTONOMOUS = "AUTONOMOUS"


class ExecutionAlgo(str, Enum):
    MARKET = "MARKET"
    TWAP = "TWAP"
    VWAP = "VWAP"
    POV = "POV"
    IS = "IS"
    PASSIVE = "PASSIVE"
    AGGRESSIVE = "AGGRESSIVE"


@dataclass(frozen=True)
class TradingMandate:
    account_id: str
    universe: tuple[str, ...]
    allowed_modes: frozenset[AutonomyMode]

    max_position_notional: Decimal
    max_order_notional: Decimal
    max_daily_turnover: Decimal

    allowed_short: bool = False

    allowed_order_types: frozenset[str] = frozenset(
        {
            "MARKET",
            "LIMIT",
        }
    )

    max_orders_per_day: int = 100

    required_confidence: float = 0.60

    allowed_horizons: tuple[
        str,
        ...
    ] = field(
        default_factory=lambda: (
            "1d",
            "1w",
            "1m",
        )
    )

    # --- FINAGENT trader-mandate extensions (all optional, backward compatible) ---
    capital: Decimal = Decimal("0")
    primary_horizon: str = "1w"
    secondary_horizon: str = "1m"
    max_position_pct: float = 0.10
    max_order_pct: float = 0.03
    max_drawdown_pct: float = 0.15
    allow_leverage: bool = False
    execution_mode: str = "SUPERVISED"
    preferred_algo: str = "VWAP"
    autonomy_enabled: bool = False
    autonomy_expiry: str = ""
    include_existing_portfolio: bool = True

    def __post_init__(self) -> None:
        if not self.account_id:
            raise ValueError("account_id cannot be empty.")
        if not self.universe:
            raise ValueError("universe cannot be empty.")
        if not 0.0 <= self.required_confidence <= 1.0:
            raise ValueError("required_confidence must be in [0,1].")
        if not 0.0 < self.max_position_pct <= 1.0:
            raise ValueError("max_position_pct must be in (0,1].")
        if not 0.0 < self.max_order_pct <= 1.0:
            raise ValueError("max_order_pct must be in (0,1].")
        if self.max_order_pct > self.max_position_pct:
            raise ValueError("max_order_pct cannot exceed max_position_pct.")
        if self.capital < Decimal("0"):
            raise ValueError("capital cannot be negative.")
        if self.execution_mode not in {m.value for m in AutonomyMode} | {
            m.value for m in ExecutionMode
        }:
            raise ValueError(f"unknown execution_mode: {self.execution_mode}")
        if self.autonomy_enabled and self.execution_mode != AutonomyMode.AUTONOMOUS.value:
            raise ValueError("autonomy_enabled requires execution_mode=AUTONOMOUS.")

    @property
    def max_position_notional_effective(self) -> Decimal:
        """Mandate pct cap applied to capital, intersected with notional cap."""
        if self.capital > 0:
            pct_cap = self.capital * Decimal(str(self.max_position_pct))
            return min(pct_cap, self.max_position_notional)
        return self.max_position_notional

    @property
    def max_order_notional_effective(self) -> Decimal:
        if self.capital > 0:
            pct_cap = self.capital * Decimal(str(self.max_order_pct))
            return min(pct_cap, self.max_order_notional)
        return self.max_order_notional

    def to_risk_overrides(self) -> dict:
        """Most-restrictive-wins mapping consumed by RiskLimits.from_mandate()."""
        return {
            "max_order_notional": self.max_order_notional_effective,
            "max_position_notional": self.max_position_notional_effective,
        }
