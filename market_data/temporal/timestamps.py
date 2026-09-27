from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


def require_utc(value: datetime) -> datetime:
    """
    Normalize an aware datetime to UTC.

    Naive timestamps are rejected deliberately.
    Research systems must never silently assume a timezone.
    """
    if value.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")

    return value.astimezone(timezone.utc)


@dataclass(frozen=True, slots=True)
class EventTime:
    """
    Exchange/event timestamp.

    When:
        When the underlying event actually occurred.
    """

    value: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", require_utc(self.value))


@dataclass(frozen=True, slots=True)
class AvailabilityTime:
    """
    Point-in-time availability timestamp.

    When:
        When DELTA could actually have observed the information.
    """

    value: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", require_utc(self.value))


@dataclass(frozen=True, slots=True)
class IngestionTime:
    """
    Timestamp at which DELTA ingested the observation.
    """

    value: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", require_utc(self.value))


@dataclass(frozen=True, slots=True)
class TemporalRecord:
    """
    Three-clock representation of a market/research observation.

    event_time:
        When reality happened.

    available_at:
        When the information became legally/operationally observable.

    ingested_at:
        When DELTA received/stored it.
    """

    event_time: EventTime
    available_at: AvailabilityTime
    ingested_at: IngestionTime

    def __post_init__(self) -> None:
        if self.available_at.value < self.event_time.value:
            raise ValueError(
                "available_at cannot precede event_time"
            )

        if self.ingested_at.value < self.available_at.value:
            raise ValueError(
                "ingested_at cannot precede available_at"
            )