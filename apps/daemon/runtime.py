from __future__ import annotations

import signal
import threading
from dataclasses import dataclass
from enum import StrEnum
from typing import Callable

from core.events.event import Event
from core.events.event_bus import EventBus
from core.events.event_types import EventType


class DaemonState(StrEnum):
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class DaemonStatus:
    state: DaemonState
    processed_events: int
    failed_events: int


class DeltaDaemon:
    """
    Event-driven DELTA runtime.

    Event subscriptions use the project's EventType contract,
    preventing invalid string event types from entering the EventBus.
    """

    def __init__(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus
        self._state = DaemonState.STOPPED
        self._processed_events = 0
        self._failed_events = 0
        self._lock = threading.RLock()
        self._stop_event = threading.Event()

    @property
    def state(self) -> DaemonState:
        with self._lock:
            return self._state

    def register_handler(
        self,
        event_type: EventType,
        handler: Callable[[Event], None],
    ) -> None:
        self._event_bus.subscribe(event_type, handler)

    def start(self) -> None:
        with self._lock:
            if self._state == DaemonState.RUNNING:
                return

            self._state = DaemonState.STARTING
            self._stop_event.clear()
            self._state = DaemonState.RUNNING

    def stop(self) -> None:
        with self._lock:
            if self._state == DaemonState.STOPPED:
                return

            self._state = DaemonState.STOPPING
            self._stop_event.set()
            self._state = DaemonState.STOPPED

    def status(self) -> DaemonStatus:
        with self._lock:
            return DaemonStatus(
                state=self._state,
                processed_events=self._processed_events,
                failed_events=self._failed_events,
            )

    def process(self, event: Event) -> None:
        if self.state != DaemonState.RUNNING:
            raise RuntimeError("DELTA daemon is not running.")

        try:
            self._event_bus.publish(event)

            with self._lock:
                self._processed_events += 1

        except Exception:
            with self._lock:
                self._failed_events += 1
            raise

    def install_signal_handlers(self) -> None:
        def shutdown(_signum: int, _frame: object) -> None:
            self.stop()

        signal.signal(signal.SIGINT, shutdown)
        signal.signal(signal.SIGTERM, shutdown)