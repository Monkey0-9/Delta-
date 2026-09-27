from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from .currency import Currency


@dataclass(frozen=True, slots=True)
class Price:
    value: Decimal
    currency: Currency

    def __post_init__(self) -> None:
        if self.value < 0:
            raise ValueError("Price cannot be negative.")