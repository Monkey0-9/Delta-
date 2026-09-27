from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from core.domain.timestamp import ensure_utc, utc_now


@dataclass(frozen=True, slots=True)
class Trade:
    instrument_id: UUID
    price: Decimal
    quantity: Decimal
    event_time: datetime = field(default_factory=utc_now)
    received_time: datetime = field(default_factory=utc_now)
    source: str = "unknown"
    schema_version: int = 1
    event_id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        if self.price <= 0:
            raise ValueError("trade price must be positive.")
        if self.quantity <= 0:
            raise ValueError("trade quantity must be positive.")
        object.__setattr__(self, "event_time", ensure_utc(self.event_time))
        object.__setattr__(self, "received_time", ensure_utc(self.received_time))
