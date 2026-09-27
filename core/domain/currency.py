from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Currency:
    """
    ISO 4217 currency representation.

    Examples:
        USD - United States Dollar
        INR - Indian Rupee
        AED - United Arab Emirates Dirham
        EUR - Euro
        GBP - Pound Sterling
        JPY - Japanese Yen
    """

    code: str

    def __post_init__(self) -> None:
        code = self.code.upper().strip()

        if len(code) != 3 or not code.isalpha():
            raise ValueError(
                f"Invalid ISO 4217 currency code: {self.code}"
            )

        object.__setattr__(self, "code", code)

    def __str__(self) -> str:
        return self.code