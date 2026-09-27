from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from brokers.interface.broker import MarketSnapshot


@dataclass(slots=True)
class SimulatedMarket:
    snapshots: dict[UUID, MarketSnapshot]

    def update(
        self,
        snapshot: MarketSnapshot,
    ) -> None:
        self.snapshots[snapshot.instrument_id] = snapshot

    def get(
        self,
        instrument_id: UUID,
    ) -> MarketSnapshot:
        try:
            return self.snapshots[instrument_id]
        except KeyError as exc:
            raise KeyError(
                f"No market data for {instrument_id}"
            ) from exc