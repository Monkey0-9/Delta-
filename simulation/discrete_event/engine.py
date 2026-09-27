"""Discrete Event Engine for simulation backtesting."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import StrEnum, auto
from enum import Enum
from heapq import heappush, heappop
from typing import Any, Callable
from uuid import UUID, uuid4
import threading


class EventType(StrEnum):
    """Types of simulation events."""
    MARKET_DATA = "market_data"
    ORDER_SUBMIT = "order_submit"
    ORDER_FILL = "order_fill"
    ORDER_CANCEL = "order_cancel"
    ORDER_REPLACE = "order_replace"
    TIMER = "timer"
    CUSTOM = "custom"


class EventPriority(Enum):
    """Priority levels for events."""
    CRITICAL = auto()  # Risk checks, emergency stops
    HIGH = auto()     # Order execution, fills
    NORMAL = auto()   # Market data, analytics
    LOW = auto()      # Logging, background tasks


@dataclass(frozen=True, slots=True, order=True)
class Event:
    """
    Discrete event with timestamp and priority.
    
    Ordered by timestamp first, then priority for same-timestamp events.
    """
    timestamp: datetime
    priority: EventPriority = EventPriority.NORMAL
    event_type: EventType = EventType.CUSTOM
    event_id: UUID = field(default_factory=uuid4)
    payload: dict[str, Any] = field(default_factory=dict)
    callback: Callable | None = None
    
    def __lt__(self, other: Event) -> bool:
        """Compare events for priority queue ordering."""
        if self.timestamp != other.timestamp:
            return self.timestamp < other.timestamp
        return self.priority.value < other.priority.value


class DiscreteEventEngine:
    """
    Deterministic discrete-event simulation engine.
    
    Implements event-driven simulation with:
    - Priority queue for event scheduling
    - Deterministic execution order
    - Simulated latencies
    - Cancel-replace dynamics
    """
    
    def __init__(self, start_time: datetime | None = None) -> None:
        self._start_time = start_time or datetime.now(timezone.utc)
        self._current_time = self._start_time
        self._event_queue: list[Event] = []
        self._event_handlers: dict[EventType, list[Callable]] = {}
        self._running = False
        self._lock = threading.Lock()
        self._event_count = 0
        self._processed_events: list[Event] = []
    
    def schedule_event(
        self,
        event: Event
    ) -> None:
        """Schedule an event for future execution."""
        with self._lock:
            heappush(self._event_queue, event)
            self._event_count += 1
    
    def schedule_at(
        self,
        timestamp: datetime,
        event_type: EventType,
        payload: dict[str, Any] | None = None,
        priority: EventPriority = EventPriority.NORMAL,
        callback: Callable | None = None
    ) -> Event:
        """Schedule an event at a specific timestamp."""
        event = Event(
            timestamp=timestamp,
            priority=priority,
            event_type=event_type,
            payload=payload or {},
            callback=callback
        )
        self.schedule_event(event)
        return event
    
    def schedule_after(
        self,
        delay: timedelta,
        event_type: EventType,
        payload: dict[str, Any] | None = None,
        priority: EventPriority = EventPriority.NORMAL,
        callback: Callable | None = None
    ) -> Event:
        """Schedule an event after a delay from current time."""
        timestamp = self._current_time + delay
        return self.schedule_at(timestamp, event_type, payload, priority, callback)
    
    def register_handler(
        self,
        event_type: EventType,
        handler: Callable
    ) -> None:
        """Register a handler for a specific event type."""
        with self._lock:
            if event_type not in self._event_handlers:
                self._event_handlers[event_type] = []
            self._event_handlers[event_type].append(handler)
    
    def run(self, end_time: datetime | None = None, max_events: int | None = None) -> None:
        """
        Run the simulation until end_time or max_events.
        
        Processes events in timestamp order, executing registered handlers.
        """
        self._running = True
        
        while self._running and self._event_queue:
            # Check termination conditions
            if end_time and self._current_time >= end_time:
                break
            
            if max_events and len(self._processed_events) >= max_events:
                break
            
            # Get next event
            with self._lock:
                if not self._event_queue:
                    break
                
                event = heappop(self._event_queue)
                self._current_time = event.timestamp
            
            # Process event
            self._process_event(event)
            self._processed_events.append(event)
        
        self._running = False
    
    def _process_event(self, event: Event) -> None:
        """Process a single event."""
        # Execute callback if provided
        if event.callback:
            try:
                event.callback(event)
            except Exception as e:
                print(f"Error in event callback: {e}")
        
        # Execute registered handlers
        handlers = self._event_handlers.get(event.event_type, [])
        for handler in handlers:
            try:
                handler(event)
            except Exception as e:
                print(f"Error in event handler: {e}")
    
    def stop(self) -> None:
        """Stop the simulation."""
        self._running = False
    
    def get_current_time(self) -> datetime:
        """Get current simulation time."""
        return self._current_time
    
    def get_pending_events(self) -> list[Event]:
        """Get all pending events (for inspection)."""
        with self._lock:
            return sorted(self._event_queue)
    
    def get_statistics(self) -> dict[str, Any]:
        """Get simulation statistics."""
        with self._lock:
            return {
                "current_time": self._current_time,
                "total_scheduled": self._event_count,
                "pending_count": len(self._event_queue),
                "processed_count": len(self._processed_events),
                "handlers_registered": {
                    event_type.value: len(handlers)
                    for event_type, handlers in self._event_handlers.items()
                },
            }
    
    def reset(self) -> None:
        """Reset the simulation to initial state."""
        with self._lock:
            self._event_queue.clear()
            self._current_time = self._start_time
            self._event_count = 0
            self._processed_events.clear()
            self._running = False
