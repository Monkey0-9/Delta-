from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from core.domain.timestamp import ensure_utc


@dataclass(frozen=True, slots=True)
class RegimeState:
    name: str
    confidence: Decimal
    timestamp: datetime

    def __post_init__(self) -> None:
        name = self.name.strip().lower()

        if not name:
            raise ValueError("regime name cannot be empty.")

        if not Decimal("0") <= self.confidence <= Decimal("1"):
            raise ValueError(
                "regime confidence must be between 0 and 1."
            )

        object.__setattr__(self, "name", name)
        object.__setattr__(
            self,
            "timestamp",
            ensure_utc(self.timestamp),
        )