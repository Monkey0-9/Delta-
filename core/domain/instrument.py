from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

from .asset_class import AssetClass
from .currency import Currency


@dataclass(frozen=True, slots=True)
class Instrument:
    instrument_id: UUID
    symbol: str
    asset_class: AssetClass
    currency: Currency
    exchange: str | None = None

    @classmethod
    def create(
        cls,
        symbol: str,
        asset_class: AssetClass,
        currency: Currency,
        exchange: str | None = None,
    ) -> Instrument:
        normalized_symbol = symbol.strip().upper()

        if not normalized_symbol:
            raise ValueError(
                "Instrument symbol cannot be empty."
            )

        return cls(
            instrument_id=uuid4(),
            symbol=normalized_symbol,
            asset_class=asset_class,
            currency=currency,
            exchange=exchange,
        )