from __future__ import annotations

import json
from pathlib import Path
from threading import Lock
from typing import Iterable

from core.events.event import Event


class EventStore:
    """
    Append-only durable event journal.

    One JSON event per line.

    This is intentionally simple and deterministic as the first
    implementation. The abstraction allows a later native/durable
    backend without changing domain code.
    """

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._lock = Lock()

        self._path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self._path.touch(exist_ok=True)

    def append(self, event: Event) -> None:
        record = {
            "event_id": str(event.event_id),
            "event_type": event.event_type,
            "payload": event.payload,
            "event_time": event.event_time.isoformat(),
            "received_time": event.received_time.isoformat(),
            "source": event.source,
            "correlation_id": (
                str(event.correlation_id)
                if event.correlation_id
                else None
            ),
            "causation_id": (
                str(event.causation_id)
                if event.causation_id
                else None
            ),
            "schema_version": event.schema_version,
        }

        encoded = json.dumps(
            record,
            sort_keys=True,
            separators=(",", ":"),
        )

        with self._lock:
            with self._path.open(
                "a",
                encoding="utf-8",
            ) as handle:
                handle.write(encoded)
                handle.write("\n")

    def read_raw(self) -> Iterable[dict]:
        with self._lock:
            with self._path.open(
                "r",
                encoding="utf-8",
            ) as handle:
                for line in handle:
                    line = line.strip()

                    if line:
                        yield json.loads(line)

    def replay(
        self,
        *,
        as_of: str | None = None,
        event_type: str | None = None,
        correlation_id: str | None = None,
    ) -> Iterable[dict]:
        """Filtered deterministic replay over the JSONL journal.

        Filters are conjunctive; ``as_of`` keeps records with
        ``event_time <= as_of`` (ISO-8601). Results are returned in file
        order so replay is bit-deterministic.
        """
        for record in self.read_raw():
            if event_type is not None and record.get("event_type") != event_type:
                continue
            if correlation_id is not None and record.get("correlation_id") != correlation_id:
                continue
            if as_of is not None and str(record.get("event_time", "")) > as_of:
                continue
            yield record