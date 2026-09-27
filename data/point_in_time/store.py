from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from hashlib import sha256


@dataclass(frozen=True, slots=True)
class StoredEvent:
    event_id: str
    event_time: datetime
    received_time: datetime
    effective_time: datetime
    source: str
    payload: str  # canonical JSON


@dataclass(slots=True)
class PointInTimeStore:
    """As-of store: research may only see effective_time <= decision time."""

    _events: list[StoredEvent] = field(default_factory=list)
    _ids: set[str] = field(default_factory=set)

    def append(self, event: StoredEvent) -> bool:
        if event.event_id in self._ids:
            return False  # deterministic duplicate drop
        if event.received_time < event.event_time:
            raise ValueError("received_time precedes event_time.")
        self._ids.add(event.event_id)
        self._events.append(event)
        return True

    def correct(self, event: StoredEvent) -> None:
        """Late-arrival correction: same id, newer received_time supersedes.

        Fail-closed: id must already exist and correction must not predate
        the original receipt (preserves audit order).
        """
        for i, existing in enumerate(self._events):
            if existing.event_id == event.event_id:
                if event.received_time < existing.received_time:
                    raise ValueError("correction predates original receipt.")
                self._events[i] = event
                return
        raise KeyError(f"unknown event_id: {event.event_id}")

    def as_of(self, decision_time: datetime) -> tuple[StoredEvent, ...]:
        visible = [e for e in self._events if e.effective_time <= decision_time]
        return tuple(sorted(visible, key=lambda e: (e.effective_time, e.event_id)))

    def dataset_hash(self) -> str:
        h = sha256()
        for e in sorted(self._events, key=lambda e: e.event_id):
            h.update(f"{e.event_id}|{e.effective_time.isoformat()}|{e.payload}".encode())
        return h.hexdigest()

    def persist(self, db_path: str) -> int:
        """Persist all events into the SQLite PIT table (migration v2)."""
        from pathlib import Path

        from storage.database.connection import Database

        db = Database(Path(db_path))
        conn = db.connect()
        n = 0
        for e in self._events:
            conn.execute(
                "INSERT INTO pit_events (event_id, event_time_utc, received_time_utc,"
                " effective_time_utc, source, payload) VALUES (?, ?, ?, ?, ?, ?)"
                " ON CONFLICT(event_id) DO UPDATE SET payload=excluded.payload,"
                " effective_time_utc=excluded.effective_time_utc",
                (
                    e.event_id,
                    e.event_time.isoformat(),
                    e.received_time.isoformat(),
                    e.effective_time.isoformat(),
                    e.source,
                    e.payload,
                ),
            )
            n += 1
        conn.commit()
        db.close()
        return n
