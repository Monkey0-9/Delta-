from datetime import datetime, timezone
import pytest

from market_data.temporal.timestamps import (
    AvailabilityTime,
    EventTime,
    IngestionTime,
    TemporalRecord,
)


def ts(value: str) -> datetime:
    return datetime.fromisoformat(value).replace(tzinfo=timezone.utc)


def test_temporal_record_normalizes_to_utc():
    record = TemporalRecord(
        event_time=EventTime(ts("2026-01-01T10:00:00")),
        available_at=AvailabilityTime(ts("2026-01-01T10:01:00")),
        ingested_at=IngestionTime(ts("2026-01-01T10:02:00")),
    )
    assert record.event_time.value.tzinfo == timezone.utc


def test_available_time_cannot_precede_event_time():
    with pytest.raises(ValueError):
        TemporalRecord(
            event_time=EventTime(ts("2026-01-01T10:00:00")),
            available_at=AvailabilityTime(ts("2026-01-01T09:59:00")),
            ingested_at=IngestionTime(ts("2026-01-01T10:02:00")),
        )


def test_ingestion_time_cannot_precede_availability_time():
    with pytest.raises(ValueError):
        TemporalRecord(
            event_time=EventTime(ts("2026-01-01T10:00:00")),
            available_at=AvailabilityTime(ts("2026-01-01T10:02:00")),
            ingested_at=IngestionTime(ts("2026-01-01T10:01:00")),
        )
