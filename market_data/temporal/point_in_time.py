from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Generic, TypeVar

from .timestamps import TemporalRecord


T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class PointInTimeObservation(Generic[T]):
    """
    An observation that can be queried according to information
    availability rather than merely event date.
    """

    value: T
    temporal: TemporalRecord
    source: str
    version: str

    def observable_at(self, as_of: datetime) -> bool:
        """
        True if the observation was available to DELTA at `as_of`.
        """
        return self.temporal.available_at.value <= as_of

    def ingested_by(self, as_of: datetime) -> bool:
        """
        True if DELTA had physically ingested the observation.
        """
        return self.temporal.ingested_at.value <= as_of

    def event_occurred_by(self, as_of: datetime) -> bool:
        """
        True if the event occurred by `as_of`.
        """
        return self.temporal.event_time.value <= as_of

    def latency(self) -> timedelta:
        """
        Time difference between event time and availability time.
        """
        return self.temporal.available_at.value - self.temporal.event_time.value

    def ingestion_latency(self) -> timedelta:
        """
        Time difference between availability time and ingestion time.
        """
        return self.temporal.ingested_at.value - self.temporal.available_at.value