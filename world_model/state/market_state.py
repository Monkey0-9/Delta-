from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from core.domain.timestamp import ensure_utc


@dataclass(frozen=True, slots=True)
class MarketState:
    symbol: str
    price: Decimal
    volatility: Decimal
    liquidity_score: Decimal
    timestamp: datetime

    def __post_init__(self) -> None:
        symbol = self.symbol.strip().upper()

        if not symbol:
            raise ValueError("symbol cannot be empty.")

        if self.price < Decimal("0"):
            raise ValueError("price cannot be negative.")

        if self.volatility < Decimal("0"):
            raise ValueError("volatility cannot be negative.")

        if not Decimal("0") <= self.liquidity_score <= Decimal("1"):
            raise ValueError(
                "liquidity_score must be between 0 and 1."
            )

        object.__setattr__(self, "symbol", symbol)

        object.__setattr__(
            self,
            "timestamp",
            ensure_utc(self.timestamp),
        )