"""
Asynchronous publish/subscribe event bus for decoupled component communication
"""

import asyncio
from typing import Dict, List, Callable, Any, Optional
from dataclasses import dataclass
from enum import Enum
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class EventType(Enum):
    """System event types"""
    # Market data events
    MARKET_DATA_UPDATE = "market_data_update"
    QUOTE_RECEIVED = "quote_received"
    BAR_RECEIVED = "bar_received"
    
    # Trading events
    ORDER_SUBMITTED = "order_submitted"
    ORDER_FILLED = "order_filled"
    ORDER_CANCELLED = "order_cancelled"
    POSITION_OPENED = "position_opened"
    POSITION_CLOSED = "position_closed"
    
    # System events
    KILL_SWITCH_TRIGGERED = "kill_switch_triggered"
    MODE_CHANGED = "mode_changed"
    MODEL_SWITCHED = "model_switched"
    BROKER_CONNECTED = "broker_connected"
    BROKER_DISCONNECTED = "broker_disconnected"
    
    # Risk events
    RISK_LIMIT_BREACHED = "risk_limit_breached"
    DRAWDOWN_LIMIT_REACHED = "drawdown_limit_reached"
    ANTI_TILT_TRIGGERED = "anti_tilt_triggered"
    
    # AI events
    MODEL_RESPONSE = "model_response"
    MODEL_ERROR = "model_error"


@dataclass
class Event:
    """Base event structure"""
    event_type: EventType
    data: Dict[str, Any]
    timestamp: datetime
    source: str = "system"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type.value,
            "data": self.data,
            "timestamp": self.timestamp.isoformat(),
            "source": self.source
        }


class EventBus:
    """Asynchronous event bus for pub/sub messaging"""
    
    def __init__(self):
        self._subscribers: Dict[EventType, List[Callable]] = {}
        self._event_queue: asyncio.Queue = asyncio.Queue()
        self._running: bool = False
        self._worker_task: Optional[asyncio.Task] = None
    
    def subscribe(self, event_type: EventType, callback: Callable) -> None:
        """Subscribe to an event type"""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(callback)
        logger.debug(f"Subscribed to {event_type.value}: {callback.__name__}")
    
    def unsubscribe(self, event_type: EventType, callback: Callable) -> None:
        """Unsubscribe from an event type"""
        if event_type in self._subscribers:
            self._subscribers[event_type].remove(callback)
            logger.debug(f"Unsubscribed from {event_type.value}: {callback.__name__}")
    
    async def publish(self, event: Event) -> None:
        """Publish an event to the bus"""
        await self._event_queue.put(event)
        logger.debug(f"Published event: {event.event_type.value}")
    
    def publish_sync(self, event: Event) -> None:
        """Synchronously publish an event (for non-async contexts)"""
        asyncio.create_task(self.publish(event))
    
    async def _process_events(self) -> None:
        """Process events from the queue"""
        while self._running:
            try:
                event = await asyncio.wait_for(self._event_queue.get(), timeout=0.1)
                await self._dispatch_event(event)
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Error processing event: {e}")
    
    async def _dispatch_event(self, event: Event) -> None:
        """Dispatch event to all subscribers"""
        if event.event_type in self._subscribers:
            for callback in self._subscribers[event.event_type]:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(event)
                    else:
                        callback(event)
                except Exception as e:
                    logger.error(f"Error in event callback {callback.__name__}: {e}")
    
    async def start(self) -> None:
        """Start the event bus worker"""
        self._running = True
        self._worker_task = asyncio.create_task(self._process_events())
        logger.info("Event bus started")
    
    async def stop(self) -> None:
        """Stop the event bus worker"""
        self._running = False
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        logger.info("Event bus stopped")
    
    def get_subscriber_count(self, event_type: EventType) -> int:
        """Get the number of subscribers for an event type"""
        return len(self._subscribers.get(event_type, []))
    
    def list_subscriptions(self) -> Dict[str, int]:
        """List all event types and their subscriber counts"""
        return {
            event_type.value: len(callbacks)
            for event_type, callbacks in self._subscribers.items()
        }


# Global event bus instance
event_bus = EventBus()
