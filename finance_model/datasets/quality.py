from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Sequence


@dataclass(frozen=True, slots=True)
class QualityReport:
    total: int
    duplicates: int
    temporal_violations: int
    missing_available_time: int

    @property
    def valid(self) -> bool:
        return (
            self.duplicates == 0
            and self.temporal_violations == 0
        )


@dataclass(frozen=True, slots=True)
class DatasetRecord:
    record_id: str
    event_time: datetime | None
    available_time: datetime | None


def validate_records(
    records: Sequence[DatasetRecord],
) -> QualityReport:
    ids = [record.record_id for record in records]

    duplicates = len(ids) - len(set(ids))

    temporal_violations = sum(
        1
        for record in records
        if (
            record.event_time is not None
            and record.available_time is not None
            and record.available_time < record.event_time
        )
    )

    missing_available_time = sum(
        1
        for record in records
        if record.available_time is None
    )

    return QualityReport(
        total=len(records),
        duplicates=duplicates,
        temporal_violations=temporal_violations,
        missing_available_time=missing_available_time,
    )