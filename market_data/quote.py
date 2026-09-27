from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from core.domain.timestamp import ensure_utc, utc_now


@dataclass(frozen=True, slots=True)
class Quote:
    instrument_id: UUID
    bid: Decimal
    ask: Decimal
    bid_size: Decimal = Decimal("0")
    ask_size: Decimal = Decimal("0")
    event_time: datetime = field(default_factory=utc_now)
    received_time: datetime = field(default_factory=utc_now)
    source: str = "unknown"
    schema_version: int = 1
    event_id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        if self.bid < 0 or self.ask < 0:
            raise ValueError("bid/ask cannot be negative.")
        if self.ask < self.bid:
            raise ValueError("ask cannot be lower than bid (crossed market).")
        if self.bid_size < 0 or self.ask_size < 0:
            raise ValueError("sizes cannot be negative.")
        object.__setattr__(self, "event_time", ensure_utc(self.event_time))
        object.__setattr__(self, "received_time", ensure_utc(self.received_time))
        if self.received_time < self.event_time:
            raise ValueError("received_time cannot precede event_time.")

    @property
    def mid(self) -> Decimal:
        return (self.bid + self.ask) / Decimal("2")

    @property
    def spread(self) -> Decimal:
        return self.ask - self.bid

    @property
    def is_crossed(self) -> bool:
        return self.ask < self.bid
