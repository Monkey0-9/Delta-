from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from core.domain.timestamp import ensure_utc, utc_now


@dataclass(frozen=True, slots=True)
class Bar:
    instrument_id: UUID
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    event_time: datetime = field(default_factory=utc_now)
    received_time: datetime = field(default_factory=utc_now)
    source: str = "unknown"
    schema_version: int = 1
    event_id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        for name in ("open", "high", "low", "close", "volume"):
            if getattr(self, name) < 0:
                raise ValueError(f"{name} cannot be negative.")
        if self.high < max(self.open, self.close, self.low):
            raise ValueError("high is inconsistent with OHLC.")
        if self.low > min(self.open, self.close, self.high):
            raise ValueError("low is inconsistent with OHLC.")
        object.__setattr__(self, "event_time", ensure_utc(self.event_time))
        object.__setattr__(self, "received_time", ensure_utc(self.received_time))
