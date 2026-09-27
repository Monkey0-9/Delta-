
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from core.domain.timestamp import ensure_utc


@dataclass(frozen=True, slots=True)
class ReplayEvent:
    timestamp: datetime
    sequence: int
    payload: Any

    def __post_init__(self) -> None:
        if self.sequence < 0:
            raise ValueError("Replay sequence cannot be negative.")

        object.__setattr__(
            self,
            "timestamp",
            ensure_utc(self.timestamp),
        )


def sort_replay_events(
    events: tuple[ReplayEvent, ...],
) -> tuple[ReplayEvent, ...]:
    return tuple(
        sorted(
            events,
            key=lambda event: (
                event.timestamp,
                event.sequence,
            ),
        )
    )
