from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from core.domain.timestamp import ensure_utc


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