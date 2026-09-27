"""Temporal semantics for market data: event time vs availability vs ingestion.

Point-in-time correctness requires distinguishing three instants:

- ``EventTime``: when the market event occurred (exchange timestamp).
- ``AvailabilityTime``: when the datum was first knowable (publication +
  revision lag). Nothing timestamped after this may inform a decision at it.
- ``IngestionTime``: when DELTA actually ingested the datum.

``TemporalRecord`` enforces the invariant
``event_time <= available_at <= ingested_at`` and rejects naive datetimes.
All instants are normalized to UTC on construction.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Sequence


def _require_aware(name: str, value: datetime) -> datetime:
    if not isinstance(value, datetime):
        raise ValueError(f"{name} must be a datetime, got {type(value).__name__}")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware (got naive datetime)")
    return value.astimezone(timezone.utc)


@dataclass(frozen=True, slots=True)
class _AwareInstant:
    value: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", _require_aware(type(self).__name__, self.value))


@dataclass(frozen=True, slots=True)
class EventTime(_AwareInstant):
    """When the market event occurred (exchange timestamp, UTC-normalized)."""


@dataclass(frozen=True, slots=True)
class AvailabilityTime(_AwareInstant):
    """When the datum was first knowable (publication/revision lag applied)."""


@dataclass(frozen=True, slots=True)
class IngestionTime(_AwareInstant):
    """When DELTA ingested the datum."""


@dataclass(frozen=True, slots=True)
class TemporalRecord:
    """A datum with full temporal lineage; enforces PIT ordering."""

    event_time: EventTime
    available_at: AvailabilityTime
    ingested_at: IngestionTime

    def __post_init__(self) -> None:
        if self.available_at.value < self.event_time.value:
            raise ValueError("available_at cannot precede event_time")
        if self.ingested_at.value < self.available_at.value:
            raise ValueError("ingested_at cannot precede available_at")

    def is_knowable_at(self, as_of: datetime) -> bool:
        """PIT predicate: was this datum knowable at ``as_of``?"""
        return self.available_at.value <= _require_aware("as_of", as_of)


@dataclass(frozen=True, slots=True)
class PointInTimeObservation:
    """A single value with temporal lineage and provenance.

    Visibility rule: an observation is usable at ``as_of`` iff its
    ``available_at`` has passed — never its ``event_time`` alone.
    """

    value: object
    temporal: TemporalRecord
    source: str
    version: str

    # Allow PointInTimeObservation[float] subscripting without Generic overhead.
    def __class_getitem__(cls, item: object) -> type:
        return cls

    def observable_at(self, as_of: datetime) -> bool:
        """True iff the value was knowable at ``as_of`` (PIT filter)."""
        return self.temporal.is_knowable_at(as_of)

    def event_occurred_by(self, as_of: datetime) -> bool:
        """True iff the underlying event had occurred by ``as_of``."""
        return self.temporal.event_time.value <= _require_aware("as_of", as_of)

    def latency(self) -> timedelta:
        """Publication lag: available_at - event_time."""
        return self.temporal.available_at.value - self.temporal.event_time.value

    def ingestion_latency(self) -> timedelta:
        """Ingestion lag: ingested_at - available_at."""
        return self.temporal.ingested_at.value - self.temporal.available_at.value


def filter_point_in_time(
    observations: Sequence[PointInTimeObservation],
    as_of: datetime,
) -> list[PointInTimeObservation]:
    """Keep only observations knowable at ``as_of`` (look-ahead guard)."""
    moment = _require_aware("as_of", as_of)
    return [obs for obs in observations if obs.observable_at(moment)]


@dataclass(frozen=True, slots=True)
class InformationSet:
    """PIT snapshot: exactly the observations visible at ``as_of``."""

    observations: tuple[PointInTimeObservation, ...]
    as_of: datetime

    def __len__(self) -> int:
        return len(self.observations)

    @classmethod
    def build(
        cls,
        observations: Sequence[PointInTimeObservation],
        as_of: datetime,
    ) -> InformationSet:
        moment = _require_aware("as_of", as_of)
        visible = filter_point_in_time(observations, moment)
        return cls(observations=tuple(visible), as_of=moment)


__all__ = [
    "AvailabilityTime",
    "EventTime",
    "InformationSet",
    "IngestionTime",
    "PointInTimeObservation",
    "TemporalRecord",
    "filter_point_in_time",
]
