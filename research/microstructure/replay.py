"""Order book replay engine for microstructure analysis.

Replays historical order book events to reconstruct market microstructure.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Callable
from enum import Enum
import time

from .order_book import Order, OrderBook, Side, OrderType, Trade
from .matching_engine import MatchingEngine, MatchResult


class EventType(str, Enum):
    """Order book event types."""
    ADD = "ADD"
    REMOVE = "REMOVE"
    MODIFY = "MODIFY"
    TRADE = "TRADE"
    SNAPSHOT = "SNAPSHOT"


@dataclass(frozen=True, slots=True)
class OrderBookEvent:
    """Order book event."""
    event_type: EventType
    timestamp: float
    symbol: str
    order_id: Optional[str] = None
    side: Optional[Side] = None
    price: Optional[float] = None
    quantity: Optional[float] = None
    trade_id: Optional[str] = None
    exchange: str = "EXCHANGE"
    sequence: int = 0


@dataclass(frozen=True, slots=True)
class ReplayConfig:
    """Replay configuration."""
    symbol: str
    start_time: float
    end_time: float
    speed_multiplier: float = 1.0
    validate_integrity: bool = True
    stop_on_error: bool = False


@dataclass
class ReplayStats:
    """Replay statistics."""
    events_processed: int = 0
    orders_added: int = 0
    orders_removed: int = 0
    orders_modified: int = 0
    trades_executed: int = 0
    errors: int = 0
    start_time: float = 0.0
    end_time: float = 0.0

    @property
    def duration(self) -> float:
        return self.end_time - self.start_time


class OrderBookReplay:
    """Order book replay engine."""

    def __init__(self, config: ReplayConfig):
        self.config = config
        self.matching_engine = MatchingEngine(config.symbol)
        self.stats = ReplayStats()
        self.event_handlers: Dict[EventType, List[Callable]] = {
            event_type: [] for event_type in EventType
        }
        self.current_time: float = config.start_time

    def add_event_handler(self, event_type: EventType, handler: Callable) -> None:
        """Add event handler for specific event type."""
        self.event_handlers[event_type].append(handler)

    def process_event(self, event: OrderBookEvent) -> Optional[MatchResult]:
        """Process a single order book event."""
        self.stats.events_processed += 1

        # Update current time
        self.current_time = event.timestamp

        try:
            result = None

            if event.event_type == EventType.ADD:
                if event.order_id and event.side and event.price and event.quantity:
                    order = Order(
                        order_id=event.order_id,
                        symbol=event.symbol,
                        side=event.side,
                        order_type=OrderType.LIMIT,
                        price=event.price,
                        quantity=event.quantity,
                        timestamp=event.timestamp,
                        exchange=event.exchange
                    )
                    result = self.matching_engine.submit_order(order)
                    self.stats.orders_added += 1

            elif event.event_type == EventType.REMOVE:
                if event.order_id:
                    success = self.matching_engine.cancel_order(event.order_id)
                    if success:
                        self.stats.orders_removed += 1

            elif event.event_type == EventType.MODIFY:
                if event.order_id and event.quantity:
                    success = self.matching_engine.order_book.modify_order(
                        event.order_id, event.quantity
                    )
                    if success:
                        self.stats.orders_modified += 1

            elif event.event_type == EventType.TRADE:
                self.stats.trades_executed += 1

            elif event.event_type == EventType.SNAPSHOT:
                # Snapshot events don't require matching
                pass

            # Call event handlers
            for handler in self.event_handlers[event.event_type]:
                handler(event, result)

            return result

        except Exception as e:
            self.stats.errors += 1
            if self.config.stop_on_error:
                raise
            return None

    def replay_events(self, events: List[OrderBookEvent]) -> ReplayStats:
        """Replay a sequence of order book events."""
        self.stats.start_time = time.time()

        # Sort events by timestamp
        sorted_events = sorted(events, key=lambda e: e.timestamp)

        for event in sorted_events:
            # Apply speed multiplier
            if self.config.speed_multiplier > 0:
                sleep_time = (event.timestamp - self.current_time) / self.config.speed_multiplier
                if sleep_time > 0:
                    time.sleep(sleep_time)

            self.process_event(event)

        self.stats.end_time = time.time()
        return self.stats

    def get_order_book_state(self) -> Dict:
        """Get current order book state."""
        return self.matching_engine.order_book.get_l2_snapshot()

    def get_trades(self) -> List[Trade]:
        """Get all trades during replay."""
        return self.matching_engine.get_trades()

    def validate_integrity(self) -> bool:
        """Validate order book integrity."""
        book = self.matching_engine.order_book

        # Check that all orders in book are referenced in orders dict
        for price, level in book.bids.items():
            for order_id in level.orders:
                if order_id not in book.orders:
                    return False

        for price, level in book.asks.items():
            for order_id in level.orders:
                if order_id not in book.orders:
                    return False

        # Check that price lists are sorted correctly
        if book._bid_prices != sorted(book._bid_prices, reverse=True):
            return False

        if book._ask_prices != sorted(book._ask_prices):
            return False

        return True

    def reset(self) -> None:
        """Reset replay engine."""
        self.matching_engine.reset()
        self.stats = ReplayStats()
        self.current_time = self.config.start_time


__all__ = [
    "EventType",
    "OrderBookEvent",
    "ReplayConfig",
    "ReplayStats",
    "OrderBookReplay",
]