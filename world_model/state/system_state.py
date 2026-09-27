from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from core.domain.timestamp import ensure_utc, utc_now

from .macro_state import MacroState
from .market_state import MarketState
from .portfolio_state import PortfolioState
from .regime_state import RegimeState
from .uncertainty_state import UncertaintyState


@dataclass(frozen=True, slots=True)
class WorldState:
    market: tuple[MarketState, ...] = ()
    macro: MacroState | None = None
    portfolio: PortfolioState | None = None
    regime: RegimeState | None = None
    uncertainty: UncertaintyState | None = None

    portfolio_equity: Decimal = Decimal("0")
    portfolio_exposure: Decimal = Decimal("0")

    version: int = 1
    timestamp: datetime | None = None

    def __post_init__(self) -> None:
        if self.version < 1:
            raise ValueError("WorldState version must be >= 1.")

        if self.portfolio_equity < Decimal("0"):
            raise ValueError(
                "portfolio_equity cannot be negative."
            )

        if self.portfolio_exposure < Decimal("0"):
            raise ValueError(
                "portfolio_exposure cannot be negative."
            )

        timestamp = (
            utc_now()
            if self.timestamp is None
            else self.timestamp
        )

        object.__setattr__(
            self,
            "timestamp",
            ensure_utc(timestamp),
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