from datetime import datetime, timezone

from market_data.temporal import (
    AvailabilityTime,
    EventTime,
    IngestionTime,
    InformationSet,
    PointInTimeObservation,
    TemporalRecord,
)


def ts(value: str) -> datetime:
    return datetime.fromisoformat(value).replace(
        tzinfo=timezone.utc
    )


def make_obs(value: float, available: str):
    available_dt = ts(available)

    return PointInTimeObservation(
        value=value,
        temporal=TemporalRecord(
            event_time=EventTime(
                available_dt
            ),
            available_at=AvailabilityTime(
                available_dt
            ),
            ingested_at=IngestionTime(
                available_dt
            ),
        ),
        source="test",
        version="v1",
    )


def test_information_set_contains_only_visible_information():
    observations = [
        make_obs(
            100.0,
            "2026-01-01T10:00:00",
        ),
        make_obs(
            200.0,
            "2026-01-02T10:00:00",
        ),
    ]

    snapshot = InformationSet.build(
        observations,
        as_of=ts("2026-01-01T12:00:00"),
    )

    assert len(snapshot) == 1
    assert snapshot.observations[0].value == 100.0