from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from .event_types import EventType
from ..domain.timestamp import ensure_utc, utc_now


@dataclass(frozen=True, slots=True)
class Event:
    event_type: EventType
    payload: dict[str, Any]

    event_id: UUID = field(default_factory=uuid4)

    event_time: datetime = field(default_factory=utc_now)
    received_time: datetime = field(default_factory=utc_now)

    source: str = "unknown"

    correlation_id: UUID | None = None
    causation_id: UUID | None = None

    schema_version: int = 1

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "event_time",
            ensure_utc(self.event_time),
        )

        object.__setattr__(
            self,
            "received_time",
            ensure_utc(self.received_time),
        )

        if self.schema_version < 1:
            raise ValueError("schema_version must be >= 1.")