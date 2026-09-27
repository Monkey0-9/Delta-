from datetime import datetime, timedelta, timezone
def observation(
    value: float,
    available: str,
) -> PointInTimeObservation[float]:
    available_dt = ts(available)

    return PointInTimeObservation(
        value=value,
        temporal=TemporalRecord(
            event_time=EventTime(
                ts("2026-01-01T09:00:00")
            ),
            available_at=AvailabilityTime(available_dt),
            ingested_at=IngestionTime(
                available_dt + timedelta(hours=2)
            ),
        ),
        source="test",
        version="v1",
    )