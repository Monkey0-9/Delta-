from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from core.domain.timestamp import ensure_utc, utc_now


@dataclass(frozen=True, slots=True)
class PositionState:
    instrument_id: UUID
    quantity: Decimal
    average_cost: Decimal
    market_price: Decimal
    updated_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        if self.quantity < Decimal("0"):
            raise ValueError("Position quantity cannot be negative.")

        if self.average_cost < Decimal("0"):
            raise ValueError("Average cost cannot be negative.")

        if self.market_price < Decimal("0"):
            raise ValueError("Market price cannot be negative.")

        object.__setattr__(
            self,
            "updated_at",
            ensure_utc(self.updated_at),
        )

    @property
    def market_value(self) -> Decimal:
        return self.quantity * self.market_price

    @property
    def unrealized_pnl(self) -> Decimal:
        return self.quantity * (
            self.market_price - self.average_cost
        )


@dataclass(frozen=True, slots=True)
class PortfolioState:
    portfolio_id: UUID = field(default_factory=uuid4)
    cash: Decimal = Decimal("0")
    positions: tuple[PositionState, ...] = ()
    updated_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        if self.cash < Decimal("0"):
            raise ValueError("Cash cannot be negative.")

        object.__setattr__(
            self,
            "updated_at",
            ensure_utc(self.updated_at),
        )

    @property
    def position_market_value(self) -> Decimal:
        return sum(
            (position.market_value for position in self.positions),
            Decimal("0"),
        )

    @property
    def equity(self) -> Decimal:
        return self.cash + self.position_market_value

    def get_position(self, instrument_id: UUID) -> PositionState | None:
        for position in self.positions:
            if position.instrument_id == instrument_id:
                return position

        return None