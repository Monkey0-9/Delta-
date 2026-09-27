from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class DataLineage:
    source_id: str
    source_type: str

    event_time: datetime | None
    available_time: datetime | None

    source_version: str
    content_hash: str

    license: str | None = None
    metadata: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if (
            self.event_time is not None
            and self.available_time is not None
            and self.available_time < self.event_time
        ):
            raise ValueError(
                "available_time cannot precede event_time"
            )


def canonical_hash(value: Any) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")

    return hashlib.sha256(payload).hexdigest()