from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from threading import RLock

from .event import Event
from .event_types import EventType


EventHandler = Callable[[Event], None]


class EventBus:
    def __init__(self) -> None:
        self._handlers: dict[
            EventType,
            list[EventHandler],
        ] = defaultdict(list)

        self._lock = RLock()

    def subscribe(
        self,
        event_type: EventType,
        handler: EventHandler,
    ) -> None:
        with self._lock:
            if handler not in self._handlers[event_type]:
                self._handlers[event_type].append(handler)

    def unsubscribe(
        self,
        event_type: EventType,
        handler: EventHandler,
    ) -> None:
        with self._lock:
            handlers = self._handlers.get(event_type, [])

            if handler in handlers:
                handlers.remove(handler)

    def publish(self, event: Event) -> None:
        with self._lock:
            handlers = tuple(
                self._handlers.get(event.event_type, ())
            )

        for handler in handlers:
            handler(event)