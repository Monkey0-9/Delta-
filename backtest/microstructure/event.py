"""
Event system for event-driven backtesting.

This defines the fundamental event types for microstructure backtesting:
- Market data events (quotes, trades, order book updates)
- Order events (new, cancel, modify)
- Fill events (execution confirmations)
- Timer events
- Custom events
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional, Any
import uuid


class EventType(Enum):
    """Event type enumeration."""
    MARKET_DATA = "MARKET_DATA"
    ORDER = "ORDER"
    FILL = "FILL"
    TIMER = "TIMER"
    SYSTEM = "SYSTEM"
    CUSTOM = "CUSTOM"


@dataclass(frozen=True, slots=True)
class Event:
    """
    Base event class.
    """
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_type: EventType = EventType.CUSTOM
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    symbol: str = ""
    metadata: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "timestamp": self.timestamp.isoformat(),
            "symbol": self.symbol,
            "metadata": self.metadata
        }


@dataclass(frozen=True, slots=True)
class MarketDataEvent(Event):
    """
    Market data event.
    """
    event_type: EventType = EventType.MARKET_DATA
    data_type: str = "QUOTE"  # QUOTE, TRADE, ORDER_BOOK
    bid_price: Optional[float] = None
    ask_price: Optional[float] = None
    bid_size: Optional[float] = None
    ask_size: Optional[float] = None
    trade_price: Optional[float] = None
    trade_size: Optional[float] = None
    mid_price: Optional[float] = None
    spread: Optional[float] = None
    
    @property
    def is_quote(self) -> bool:
        """Check if quote data."""
        return self.data_type == "QUOTE"
    
    @property
    def is_trade(self) -> bool:
        """Check if trade data."""
        return self.data_type == "TRADE"
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        base_dict = super().to_dict()
        base_dict.update({
            "data_type": self.data_type,
            "bid_price": self.bid_price,
            "ask_price": self.ask_price,
            "bid_size": self.bid_size,
            "ask_size": self.ask_size,
            "trade_price": self.trade_price,
            "trade_size": self.trade_size,
            "mid_price": self.mid_price,
            "spread": self.spread
        })
        return base_dict


@dataclass(frozen=True, slots=True)
class OrderEvent(Event):
    """
    Order event.
    """
    event_type: EventType = EventType.ORDER
    order_id: str = ""
    side: str = "BUY"  # BUY or SELL
    order_type: str = "LIMIT"  # LIMIT, MARKET, IOC, FOK
    price: Optional[float] = None
    quantity: float = 0.0
    status: str = "NEW"  # NEW, FILLED, PARTIALLY_FILLED, CANCELLED, REJECTED
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        base_dict = super().to_dict()
        base_dict.update({
            "order_id": self.order_id,
            "side": self.side,
            "order_type": self.order_type,
            "price": self.price,
            "quantity": self.quantity,
            "status": self.status
        })
        return base_dict


@dataclass(frozen=True, slots=True)
class FillEvent(Event):
    """
    Fill event (execution confirmation).
    """
    event_type: EventType = EventType.FILL
    order_id: str = ""
    fill_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    side: str = "BUY"
    price: float = 0.0
    quantity: float = 0.0
    fee: float = 0.0
    commission: float = 0.0
    venue: str = ""
    liquidity_indicator: str = "UNKNOWN"  # MAKER, TAKER, UNKNOWN
    
    @property
    def notional(self) -> float:
        """Calculate fill notional."""
        return self.price * self.quantity
    
    @property
    def total_cost(self) -> float:
        """Calculate total cost including fees."""
        return self.notional + self.fee + self.commission
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        base_dict = super().to_dict()
        base_dict.update({
            "order_id": self.order_id,
            "fill_id": self.fill_id,
            "side": self.side,
            "price": self.price,
            "quantity": self.quantity,
            "fee": self.fee,
            "commission": self.commission,
            "venue": self.venue,
            "liquidity_indicator": self.liquidity_indicator,
            "notional": self.notional,
            "total_cost": self.total_cost
        })
        return base_dict


@dataclass(frozen=True, slots=True)
class TimerEvent(Event):
    """
    Timer event for scheduled actions.
    """
    event_type: EventType = EventType.TIMER
    timer_id: str = ""
    action: str = ""
    interval_ms: int = 0
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        base_dict = super().to_dict()
        base_dict.update({
            "timer_id": self.timer_id,
            "action": self.action,
            "interval_ms": self.interval_ms
        })
        return base_dict


class EventQueue:
    """
    Priority queue for time-ordered event processing.
    
    Features:
    - Time-ordered event delivery
    - Priority-based scheduling
    - Event filtering
    """
    
    def __init__(self):
        """Initialize event queue."""
        self.events: List[Event] = []
        self.event_handlers: Dict[EventType, List] = {}
    
    def enqueue(self, event: Event) -> None:
        """
        Add event to queue.
        
        Args:
            event: Event to enqueue
        """
        self.events.append(event)
        # Sort by timestamp
        self.events.sort(key=lambda e: e.timestamp)
    
    def dequeue(self) -> Optional[Event]:
        """
        Get next event from queue.
        
        Returns:
            Next event or None if empty
        """
        if not self.events:
            return None
        
        return self.events.pop(0)
    
    def peek(self) -> Optional[Event]:
        """
        Peek at next event without removing.
        
        Returns:
            Next event or None if empty
        """
        if not self.events:
            return None
        
        return self.events[0]
    
    def register_handler(self, event_type: EventType, handler) -> None:
        """
        Register event handler for event type.
        
        Args:
            event_type: Event type to handle
            handler: Handler function
        """
        if event_type not in self.event_handlers:
            self.event_handlers[event_type] = []
        self.event_handlers[event_type].append(handler)
    
    def process_next(self) -> bool:
        """
        Process next event in queue.
        
        Returns:
            True if event was processed, False if queue empty
        """
        event = self.dequeue()
        
        if event is None:
            return False
        
        # Get handlers for event type
        handlers = self.event_handlers.get(event.event_type, [])
        
        # Call all handlers
        for handler in handlers:
            handler(event)
        
        return True
    
    def process_all(self) -> int:
        """
        Process all events in queue.
        
        Returns:
            Number of events processed
        """
        count = 0
        while self.process_next():
            count += 1
        return count
    
    def clear(self) -> None:
        """Clear all events."""
        self.events.clear()
    
    def size(self) -> int:
        """Get queue size."""
        return len(self.events)
    
    def filter_by_type(self, event_type: EventType) -> List[Event]:
        """
        Filter events by type.
        
        Args:
            event_type: Event type to filter
            
        Returns:
            List of matching events
        """
        return [e for e in self.events if e.event_type == event_type]
    
    def filter_by_symbol(self, symbol: str) -> List[Event]:
        """
        Filter events by symbol.
        
        Args:
            symbol: Symbol to filter
            
        Returns:
            List of matching events
        """
        return [e for e in self.events if e.symbol == symbol]
    
    def filter_by_time_range(self, 
                           start_time: datetime,
                           end_time: datetime) -> List[Event]:
        """
        Filter events by time range.
        
        Args:
            start_time: Start of time range
            end_time: End of time range
            
        Returns:
            List of matching events
        """
        return [
            e for e in self.events
            if start_time <= e.timestamp <= end_time
        ]


__all__ = [
    "EventType",
    "Event",
    "MarketDataEvent",
    "OrderEvent",
    "FillEvent",
    "TimerEvent",
    "EventQueue"
]