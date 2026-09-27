from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from core.domain.timestamp import ensure_utc


@dataclass(frozen=True, slots=True)
class PortfolioState:
    """
    Immutable snapshot of portfolio-level state used by WorldState.
    """

    portfolio_id: UUID
    equity: Decimal
    cash: Decimal
    gross_exposure: Decimal
    net_exposure: Decimal
    timestamp: datetime

    def __post_init__(self) -> None:
        if self.equity < Decimal("0"):
            raise ValueError("equity cannot be negative.")

        if self.cash < Decimal("0"):
            raise ValueError("cash cannot be negative.")

        if self.gross_exposure < Decimal("0"):
            raise ValueError(
                "gross_exposure cannot be negative."
            )

        if self.net_exposure < Decimal("0"):
            raise ValueError(
                "net_exposure cannot be negative."
            )

        object.__setattr__(
            self,
            "timestamp",
            ensure_utc(self.timestamp),
        )