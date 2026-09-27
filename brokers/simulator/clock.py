from __future__ import annotations

from datetime import datetime, timedelta

from core.domain.timestamp import ensure_utc


class SimulationClock:
    def __init__(self, start: datetime) -> None:
        self._current = ensure_utc(start)

    @property
    def now(self) -> datetime:
        return self._current

    def advance(self, seconds: float) -> datetime:
        if seconds < 0:
            raise ValueError(
                "Simulation time cannot move backwards."
            )

        self._current += timedelta(seconds=seconds)
        return self._current