from __future__ import annotations
from datetime import datetime, timezone

def utc_now() -> datetime:
    "returns the current UTC time as timezone-aware UTC timestamp."
    return datetime.now(timezone.utc)

def ensure_utc(value: datetime) -> datetime:
    "validates and normalizes a datetime to UTC."
    if value.tzinfo is None:
        raise ValueError("Delta requires timezone-aware datetimes.")
    return value.astimezone(timezone.utc)
