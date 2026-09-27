from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from core.domain.timestamp import ensure_utc, utc_now


@dataclass(frozen=True, slots=True)
class MarketState:
    symbol: str
    price: Decimal
    volatility: Decimal
    liquidity_score: Decimal
    timestamp: datetime

    def __post_init__(self) -> None:
        if not self.symbol.strip():
            raise ValueError("symbol cannot be empty.")

        if self.price < Decimal("0"):
            raise ValueError("price cannot be negative.")

        if not Decimal("0") <= self.volatility:
            raise ValueError("volatility cannot be negative.")

        if not Decimal("0") <= self.liquidity_score <= Decimal("1"):
            raise ValueError(
                "liquidity_score must be between 0 and 1."
            )

        object.__setattr__(
            self,
            "symbol",
            self.symbol.strip().upper(),
        )

        object.__setattr__(
            self,
            "timestamp",
            ensure_utc(self.timestamp),
        )


@dataclass(frozen=True, slots=True)
class MacroState:
    risk_free_rate: Decimal
    inflation: Decimal
    growth: Decimal
    timestamp: datetime

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "timestamp",
            ensure_utc(self.timestamp),
        )


@dataclass(frozen=True, slots=True)
class RegimeState:
    name: str
    confidence: Decimal
    timestamp: datetime

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("Regime name cannot be empty.")

        if not Decimal("0") <= self.confidence <= Decimal("1"):
            raise ValueError(
                "Regime confidence must be between 0 and 1."
            )

        object.__setattr__(
            self,
            "name",
            self.name.strip(),
        )

        object.__setattr__(
            self,
            "timestamp",
            ensure_utc(self.timestamp),
        )


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

        if any(not Decimal("0") <= value <= Decimal("1")
               for value in values):
            raise ValueError(
                "Uncertainty values must be between 0 and 1."
            )

    @property
    def aggregate(self) -> Decimal:
        return (
            self.model
            + self.data
            + self.regime
            + self.execution
        ) / Decimal("4")


@dataclass(frozen=True, slots=True)
class WorldState:
    market: tuple[MarketState, ...] = ()
    macro: MacroState | None = None
    regime: RegimeState | None = None
    uncertainty: UncertaintyState | None = None

    portfolio_equity: Decimal = Decimal("0")
    portfolio_exposure: Decimal = Decimal("0")

    state_id: UUID = field(default_factory=uuid4)
    version: int = 1
    timestamp: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        if self.version < 1:
            raise ValueError("World-state version must be >= 1.")

        if self.portfolio_equity < Decimal("0"):
            raise ValueError(
                "Portfolio equity cannot be negative."
            )

        if self.portfolio_exposure < Decimal("0"):
            raise ValueError(
                "Portfolio exposure cannot be negative."
            )

        object.__setattr__(
            self,
            "timestamp",
            ensure_utc(self.timestamp),
        )

    def market_for(
        self,
        symbol: str,
    ) -> MarketState | None:
        normalized = symbol.strip().upper()

        for state in self.market:
            if state.symbol == normalized:
                return state

        return None