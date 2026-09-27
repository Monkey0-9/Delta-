from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4


@dataclass(frozen=True, slots=True)
class Asset:
    asset_id: UUID
    symbol: str
    name: str = ""
    isin: str = ""

    @classmethod
    def create(cls, symbol: str, name: str = "", isin: str = "") -> Asset:
        sym = symbol.strip().upper()
        if not sym:
            raise ValueError("symbol cannot be empty.")
        return cls(asset_id=uuid4(), symbol=sym, name=name, isin=isin)
