from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class BacktestResult:
    initial_equity: Decimal
    final_equity: Decimal
    total_return: Decimal
    realized_pnl: Decimal
    unrealized_pnl: Decimal
    events_processed: int
    fills: int

    @property
    def profit(self) -> Decimal:
        return self.final_equity - self.initial_equity
