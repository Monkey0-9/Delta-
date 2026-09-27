from datetime import datetime, timezone

import pytest

from market_data.temporal import (
    AvailabilityTime,
    EventTime,
    IngestionTime,
    TemporalRecord,
)


def ts(value: str) -> datetime:
    return datetime.fromisoformat(value).replace(
        tzinfo=timezone.utc
    )


def test_naive_timestamp_is_rejected():
    with pytest.raises(ValueError, match="timezone-aware"):
        EventTime(
            datetime(2026, 1, 1, 9, 0)
        )


def test_timestamps_are_normalized_to_utc():
    value = datetime.fromisoformat(
        "2026-01-01T09:00:00+05:30"
    )

    result = EventTime(value)

    assert result.value == datetime.fromisoformat(
        "2026-01-01T03:30:00+00:00"
    )


def test_availability_cannot_precede_event():
    with pytest.raises(
        ValueError,
        match="available_at cannot precede event_time",
    ):
        TemporalRecord(
            event_time=EventTime(
                ts("2026-01-02T10:00:00")
            ),
            available_at=AvailabilityTime(
                ts("2026-01-02T09:00:00")
            ),
            ingested_at=IngestionTime(
                ts("2026-01-02T11:00:00")
            ),
        )


def test_ingestion_cannot_precede_availability():
    with pytest.raises(
        ValueError,
        match="ingested_at cannot precede available_at",
    ):
        TemporalRecord(
            event_time=EventTime(
                ts("2026-01-02T08:00:00")
            ),
            available_at=AvailabilityTime(
                ts("2026-01-02T10:00:00")
            ),
            ingested_at=IngestionTime(
                ts("2026-01-02T09:00:00")
            ),
        )


def test_valid_temporal_record():
    record = TemporalRecord(
        event_time=EventTime(
            ts("2026-01-02T08:00:00")
        ),
        available_at=AvailabilityTime(
            ts("2026-01-02T10:00:00")
        ),
        ingested_at=IngestionTime(
            ts("2026-01-02T10:00:05")
        ),
    )

    assert (
        record.event_time.value
        <= record.available_at.value
        <= record.ingested_at.value
    )