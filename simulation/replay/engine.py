
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from brokers.simulator.clock import SimulationClock
from simulation.replay.event import (
    ReplayEvent,
    sort_replay_events,
)


@dataclass(frozen=True, slots=True)
class ReplayStatistics:
    events_processed: int
    start_time: datetime | None
    end_time: datetime | None


class ReplayEngine:
    """
    Deterministic historical event replay.

    Responsibilities:
    - deterministic event ordering
    - deterministic simulation time
    - event delivery

    Strategy and trading logic remain outside this class.
    """

    def __init__(
        self,
        *,
        clock: SimulationClock,
    ) -> None:
        self._clock = clock

    @property
    def clock(self) -> SimulationClock:
        return self._clock

    def run(
        self,
        events: tuple[ReplayEvent, ...],
        handler: Callable[[ReplayEvent], None],
    ) -> ReplayStatistics:
        ordered = sort_replay_events(events)

        if not ordered:
            return ReplayStatistics(
                events_processed=0,
                start_time=None,
                end_time=None,
            )

        for event in ordered:
            if event.timestamp < self._clock.now:
                raise ValueError(
                    "Replay event occurs before simulation clock."
                )

            delta = (
                event.timestamp - self._clock.now
            ).total_seconds()

            if delta > 0:
                self._clock.advance(delta)

            handler(event)

        return ReplayStatistics(
            events_processed=len(ordered),
            start_time=ordered[0].timestamp,
            end_time=ordered[-1].timestamp,
        )
