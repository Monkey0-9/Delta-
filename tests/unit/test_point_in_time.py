from datetime import datetime, timezone

from market_data.temporal import (
    AvailabilityTime,
    EventTime,
    IngestionTime,
    PointInTimeObservation,
    TemporalRecord,
    filter_point_in_time,
)


def ts(value: str) -> datetime:
    return datetime.fromisoformat(value).replace(tzinfo=timezone.utc)


def observation(
    value: float,
    available: str,
) -> PointInTimeObservation[float]:
    available_dt = ts(available)
    return PointInTimeObservation(
        value=value,
        temporal=TemporalRecord(
            event_time=EventTime(ts("2026-01-01T09:00:00")),
            available_at=AvailabilityTime(available_dt),
            ingested_at=IngestionTime(
                available_dt.replace(hour=12)
            ),
        ),
        source="test",
        version="v1",
    )


def test_future_information_is_not_visible():
    obs = observation(
        100.0,
        "2026-01-02T10:00:00",
    )

    assert not obs.observable_at(
        ts("2026-01-02T09:59:59")
    )


def test_available_information_is_visible():
    obs = observation(
        100.0,
        "2026-01-02T10:00:00",
    )

    assert obs.observable_at(
        ts("2026-01-02T10:00:00")
    )


def test_filter_point_in_time():
    observations = [
        observation(100.0, "2026-01-02T10:00:00"),
        observation(200.0, "2026-01-03T10:00:00"),
    ]

    result = filter_point_in_time(
        observations,
        as_of=ts("2026-01-02T12:00:00"),
    )

    assert len(result) == 1
    assert result[0].value == 100.0
    
def test_event_time_is_not_information_availability():
    obs = observation(
        100.0,
        "2026-01-02T10:00:00",
    )

    assert obs.event_occurred_by(
        ts("2026-01-02T09:30:00")
    )

    assert not obs.observable_at(
        ts("2026-01-02T09:30:00")
    )


def test_information_latency():
    obs = observation(
        100.0,
        "2026-01-02T10:00:00",
    )

    assert obs.latency().total_seconds() == (
        25 * 3600
    )


def test_ingestion_latency():
    obs = observation(
        100.0,
        "2026-01-02T10:00:00",
    )

    assert obs.ingestion_latency().total_seconds() == (
        2 * 3600
    )