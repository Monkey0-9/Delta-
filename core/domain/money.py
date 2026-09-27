from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from .currency import Currency


@dataclass(frozen=True, slots=True)
class Money:
    amount: Decimal
    currency: Currency

    def __add__(self, other: Money) -> Money:
        self._require_same_currency(other)

        return Money(
            amount=self.amount + other.amount,
            currency=self.currency,
        )

    def __sub__(self, other: Money) -> Money:
        self._require_same_currency(other)

        return Money(
            amount=self.amount - other.amount,
            currency=self.currency,
        )

    def __neg__(self) -> Money:
        return Money(
            amount=-self.amount,
            currency=self.currency,
        )

    def _require_same_currency(self, other: Money) -> None:
        if self.currency != other.currency:
            raise ValueError(
                f"Currency mismatch: "
                f"{self.currency} != {other.currency}"
            )