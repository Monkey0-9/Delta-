from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from uuid import UUID

from .money import Money
from .position import Position


@dataclass
class Portfolio:
    """
    Current portfolio state.

    Responsibilities:
        - Track cash.
        - Track positions.
        - Calculate market value.
        - Calculate total equity.
        - Calculate unrealized P&L.

    Currency conversion is intentionally NOT performed here.
    Portfolio valuation across multiple currencies will be handled
    by the future FX/valuation subsystem.
    """

    cash: Money
    positions: dict[UUID, Position] = field(default_factory=dict)

    @property
    def market_value(self) -> Decimal:
        """Return the aggregate market value of all positions."""
        return sum(
            (
                position.market_value
                for position in self.positions.values()
            ),
            Decimal("0"),
        )

    @property
    def equity(self) -> Decimal:
        """
        Return portfolio equity.

        This assumes positions and cash are already represented
        in the portfolio's valuation currency.
        """
        return self.cash.amount + self.market_value

    @property
    def unrealized_pnl(self) -> Decimal:
        """Return aggregate unrealized P&L."""
        return sum(
            (
                position.unrealized_pnl
                for position in self.positions.values()
            ),
            Decimal("0"),
        )

    def get_position(
        self,
        instrument_id: UUID,
    ) -> Position | None:
        """Return a position by instrument ID."""
        return self.positions.get(instrument_id)