"""
L2 Order Book Engine for Event-Driven Microstructure Simulation.

This module implements a realistic L2 order book with:
- Multiple price levels (depth)
- Queue position tracking
- Price-time priority matching
- Event-driven updates
- Integration with canonical contracts
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Optional, Dict, List, Tuple
from uuid import UUID, uuid4

from core.contracts.canonical import (
    Instrument,
    Timestamps,
    Side,
    OrderType,
    OrderStatus,
    TimeInForce,
)


class OrderBookSide(Enum):
    """Order book side enumeration."""
    BID = "bid"
    ASK = "ask"


@dataclass(frozen=True, slots=True)
class PriceLevel:
    """
    Represents a single price level in the order book.
    
    Attributes:
        price: Price level
        total_quantity: Total quantity at this price level
        order_count: Number of orders at this price level
        queue_position: Position in queue (0 = front)
    """
    price: Decimal
    total_quantity: Decimal
    order_count: int
    queue_position: int = 0
    
    @property
    def avg_order_size(self) -> Decimal:
        """Average order size at this level."""
        if self.order_count == 0:
            return Decimal("0")
        return self.total_quantity / Decimal(str(self.order_count))


@dataclass(slots=True)
class LimitOrder:
    """
    Represents a limit order in the order book.
    
    Attributes:
        order_id: Unique order identifier
        side: Order side (BUY/SELL)
        price: Limit price
        quantity: Remaining quantity
        original_quantity: Original order quantity
        timestamp: Order creation timestamp
        time_in_force: Time in force instruction
        sequence: Sequence number for priority
        queue_position: Position in queue at price level
    """
    order_id: str
    side: Side
    price: Decimal
    quantity: Decimal
    original_quantity: Decimal
    timestamp: datetime
    time_in_force: TimeInForce
    sequence: int
    queue_position: int = 0
    
    @property
    def filled_quantity(self) -> Decimal:
        """Quantity already filled."""
        return self.original_quantity - self.quantity
    
    @property
    def fill_ratio(self) -> float:
        """Fill ratio (0.0 to 1.0)."""
        if self.original_quantity == 0:
            return 0.0
        return float(self.filled_quantity / self.original_quantity)


@dataclass
class OrderBookSnapshot:
    """
    Snapshot of the order book state.
    
    Attributes:
        instrument: Instrument being traded
        timestamp: Snapshot timestamp
        bids: List of bid price levels (best bid first)
        asks: List of ask price levels (best ask first)
        spread: Current spread
        mid_price: Mid price
        total_bid_volume: Total volume on bid side
        total_ask_volume: Total volume on ask side
        imbalance: Volume imbalance (bid - ask) / (bid + ask)
    """
    instrument: Instrument
    timestamp: datetime
    bids: List[PriceLevel] = field(default_factory=list)
    asks: List[PriceLevel] = field(default_factory=list)
    spread: Optional[Decimal] = None
    mid_price: Optional[Decimal] = None
    total_bid_volume: Decimal = Decimal("0")
    total_ask_volume: Decimal = Decimal("0")
    imbalance: Optional[float] = None
    
    def __post_init__(self):
        """Calculate derived metrics."""
        if self.bids and self.asks:
            best_bid = self.bids[0].price
            best_ask = self.asks[0].price
            self.spread = best_ask - best_bid
            self.mid_price = (best_bid + best_ask) / Decimal("2")
            
            self.total_bid_volume = sum(level.total_quantity for level in self.bids)
            self.total_ask_volume = sum(level.total_quantity for level in self.asks)
            
            total_volume = self.total_bid_volume + self.total_ask_volume
            if total_volume > 0:
                self.imbalance = float((self.total_bid_volume - self.total_ask_volume) / total_volume)


class L2OrderBook:
    """
    L2 Order Book with realistic microstructure simulation.
    
    Features:
    - Multiple price levels with full depth
    - Queue position tracking for each order
    - Price-time priority matching
    - Event-driven updates
    - Partial fills and cancellations
    - Time-in-force handling
    """
    
    def __init__(
        self,
        instrument: Instrument,
        max_depth: int = 20,
        tick_size: Optional[Decimal] = None
    ):
        """
        Initialize L2 order book.
        
        Args:
            instrument: Instrument being traded
            max_depth: Maximum number of price levels to track
            tick_size: Minimum price increment (None = no tick size constraint)
        """
        self._instrument = instrument
        self._max_depth = max_depth
        self._tick_size = tick_size
        
        # Order books: price -> deque of orders (FIFO queue)
        self._bids: Dict[Decimal, deque[LimitOrder]] = {}
        self._asks: Dict[Decimal, deque[LimitOrder]] = {}
        
        # Order lookup: order_id -> order
        self._orders: Dict[str, LimitOrder] = {}
        
        # Sequence counter for priority
        self._sequence = 0
        
        # Last trade price
        self._last_trade_price: Optional[Decimal] = None
        
    @property
    def instrument(self) -> Instrument:
        """Get instrument."""
        return self._instrument
    
    @property
    def best_bid(self) -> Optional[Decimal]:
        """Get best bid price."""
        if not self._bids:
            return None
        return max(self._bids.keys())
    
    @property
    def best_ask(self) -> Optional[Decimal]:
        """Get best ask price."""
        if not self._asks:
            return None
        return min(self._asks.keys())
    
    @property
    def spread(self) -> Optional[Decimal]:
        """Get current spread."""
        best_bid = self.best_bid
        best_ask = self.best_ask
        if best_bid is None or best_ask is None:
            return None
        return best_ask - best_bid
    
    @property
    def mid_price(self) -> Optional[Decimal]:
        """Get mid price."""
        best_bid = self.best_bid
        best_ask = self.best_ask
        if best_bid is None or best_ask is None:
            return None
        return (best_bid + best_ask) / Decimal("2")
    
    def add_limit_order(
        self,
        order_id: str,
        side: Side,
        price: Decimal,
        quantity: Decimal,
        time_in_force: TimeInForce = TimeInForce.GTC,
        timestamp: Optional[datetime] = None
    ) -> Tuple[List[Tuple[str, Decimal, Decimal]], Optional[LimitOrder]]:
        """
        Add a limit order to the book.
        
        Args:
            order_id: Unique order identifier
            side: Order side
            price: Limit price
            quantity: Order quantity
            time_in_force: Time in force instruction
            timestamp: Order timestamp (defaults to now)
            
        Returns:
            Tuple of (fills, remaining_order) where fills is a list of
            (matched_order_id, fill_price, fill_quantity) and remaining_order
            is the order if it didn't fully fill (None otherwise)
        """
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)
        
        if quantity <= 0:
            raise ValueError("Quantity must be positive")
        if price <= 0:
            raise ValueError("Price must be positive")
        
        # Apply tick size if specified
        if self._tick_size is not None:
            price = (price / self._tick_size).quantize(Decimal("1")) * self._tick_size
        
        self._sequence += 1
        
        # Create order
        order = LimitOrder(
            order_id=order_id,
            side=side,
            price=price,
            quantity=quantity,
            original_quantity=quantity,
            timestamp=timestamp,
            time_in_force=time_in_force,
            sequence=self._sequence
        )
        
        # Match against opposite side
        fills = self._match_order(order)
        
        # If order didn't fully fill, add to book
        if order.quantity > 0:
            self._add_to_book(order)
            return fills, order
        else:
            return fills, None
    
    def cancel_order(self, order_id: str) -> bool:
        """
        Cancel an order.
        
        Args:
            order_id: Order to cancel
            
        Returns:
            True if order was found and cancelled, False otherwise
        """
        if order_id not in self._orders:
            return False
        
        order = self._orders[order_id]
        
        # Remove from appropriate book
        book = self._bids if order.side == Side.BUY else self._asks
        
        if order.price in book:
            queue = book[order.price]
            # Remove order from queue
            for i, o in enumerate(queue):
                if o.order_id == order_id:
                    queue.remove(o)
                    # Update queue positions for remaining orders
                    for j in range(i, len(queue)):
                        # Create new order with updated queue position
                        updated_order = LimitOrder(
                            order_id=queue[j].order_id,
                            side=queue[j].side,
                            price=queue[j].price,
                            quantity=queue[j].quantity,
                            original_quantity=queue[j].original_quantity,
                            timestamp=queue[j].timestamp,
                            time_in_force=queue[j].time_in_force,
                            sequence=queue[j].sequence,
                            queue_position=j
                        )
                        queue[j] = updated_order
                        self._orders[queue[j].order_id] = updated_order
                    break
            
            # Remove price level if empty
            if not queue:
                del book[order.price]
        
        # Remove from order lookup
        del self._orders[order_id]
        
        return True
    
    def replace_order(
        self,
        order_id: str,
        new_price: Optional[Decimal] = None,
        new_quantity: Optional[Decimal] = None
    ) -> Tuple[List[Tuple[str, Decimal, Decimal]], Optional[LimitOrder]]:
        """
        Replace an order (cancel + new order, loses time priority).
        
        Args:
            order_id: Order to replace
            new_price: New price (None = keep original)
            new_quantity: New quantity (None = keep original)
            
        Returns:
            Tuple of (fills, remaining_order) from the new order
        """
        if order_id not in self._orders:
            raise ValueError(f"Order {order_id} not found")
        
        original_order = self._orders[order_id]
        
        # Cancel original order
        self.cancel_order(order_id)
        
        # Create new order with updated parameters
        new_order_id = f"{order_id}_replace_{self._sequence}"
        price = new_price if new_price is not None else original_order.price
        quantity = new_quantity if new_quantity is not None else original_order.quantity
        
        return self.add_limit_order(
            order_id=new_order_id,
            side=original_order.side,
            price=price,
            quantity=quantity,
            time_in_force=original_order.time_in_force,
            timestamp=datetime.now(timezone.utc)
        )
    
    def get_snapshot(self, depth: Optional[int] = None) -> OrderBookSnapshot:
        """
        Get current order book snapshot.
        
        Args:
            depth: Number of price levels to include (None = use max_depth)
            
        Returns:
            OrderBookSnapshot with current state
        """
        if depth is None:
            depth = self._max_depth
        
        # Get bid levels (descending)
        bid_prices = sorted(self._bids.keys(), reverse=True)[:depth]
        bids = []
        for i, price in enumerate(bid_prices):
            queue = self._bids[price]
            total_qty = sum(o.quantity for o in queue)
            bids.append(PriceLevel(
                price=price,
                total_quantity=total_qty,
                order_count=len(queue),
                queue_position=0  # Price level doesn't have queue position
            ))
        
        # Get ask levels (ascending)
        ask_prices = sorted(self._asks.keys())[:depth]
        asks = []
        for i, price in enumerate(ask_prices):
            queue = self._asks[price]
            total_qty = sum(o.quantity for o in queue)
            asks.append(PriceLevel(
                price=price,
                total_quantity=total_qty,
                order_count=len(queue),
                queue_position=0
            ))
        
        return OrderBookSnapshot(
            instrument=self._instrument,
            timestamp=datetime.now(timezone.utc),
            bids=bids,
            asks=asks
        )
    
    def get_order(self, order_id: str) -> Optional[LimitOrder]:
        """
        Get order by ID.
        
        Args:
            order_id: Order identifier
            
        Returns:
            LimitOrder if found, None otherwise
        """
        return self._orders.get(order_id)
    
    def get_queue_position(self, order_id: str) -> Optional[int]:
        """
        Get queue position for an order.
        
        Args:
            order_id: Order identifier
            
        Returns:
            Queue position (0 = front of queue) or None if order not found
        """
        order = self._orders.get(order_id)
        if order is None:
            return None
        return order.queue_position
    
    def _match_order(self, order: LimitOrder) -> List[Tuple[str, Decimal, Decimal]]:
        """
        Match order against opposite side.
        
        Args:
            order: Order to match
            
        Returns:
            List of (matched_order_id, fill_price, fill_quantity)
        """
        fills: List[Tuple[str, Decimal, Decimal]] = []
        
        if order.side == Side.BUY:
            # Match against asks
            while order.quantity > 0 and self._asks:
                best_ask = min(self._asks.keys())
                if best_ask > order.price:
                    break  # No more matching orders
                
                queue = self._asks[best_ask]
                if not queue:
                    del self._asks[best_ask]
                    continue
                
                # Match with front of queue
                resting_order = queue[0]
                fill_qty = min(order.quantity, resting_order.quantity)
                fill_price = resting_order.price
                
                fills.append((resting_order.order_id, fill_price, fill_qty))
                
                # Update quantities
                order.quantity -= fill_qty
                resting_order.quantity -= fill_qty
                
                # Update resting order in lookup
                self._orders[resting_order.order_id] = resting_order
                
                # Remove filled order
                if resting_order.quantity <= 0:
                    queue.popleft()
                    del self._orders[resting_order.order_id]
                    
                    # Remove price level if empty
                    if not queue:
                        del self._asks[best_ask]
                
                self._last_trade_price = fill_price
                
        else:  # SELL
            # Match against bids
            while order.quantity > 0 and self._bids:
                best_bid = max(self._bids.keys())
                if best_bid < order.price:
                    break  # No more matching orders
                
                queue = self._bids[best_bid]
                if not queue:
                    del self._bids[best_bid]
                    continue
                
                # Match with front of queue
                resting_order = queue[0]
                fill_qty = min(order.quantity, resting_order.quantity)
                fill_price = resting_order.price
                
                fills.append((resting_order.order_id, fill_price, fill_qty))
                
                # Update quantities
                order.quantity -= fill_qty
                resting_order.quantity -= fill_qty
                
                # Update resting order in lookup
                self._orders[resting_order.order_id] = resting_order
                
                # Remove filled order
                if resting_order.quantity <= 0:
                    queue.popleft()
                    del self._orders[resting_order.order_id]
                    
                    # Remove price level if empty
                    if not queue:
                        del self._bids[best_bid]
                
                self._last_trade_price = fill_price
        
        return fills
    
    def _add_to_book(self, order: LimitOrder) -> None:
        """
        Add order to appropriate book.
        
        Args:
            order: Order to add
        """
        book = self._bids if order.side == Side.BUY else self._asks
        
        if order.price not in book:
            book[order.price] = deque()
        
        # Set queue position
        queue_position = len(book[order.price])
        
        # Create order with queue position
        order_with_position = LimitOrder(
            order_id=order.order_id,
            side=order.side,
            price=order.price,
            quantity=order.quantity,
            original_quantity=order.original_quantity,
            timestamp=order.timestamp,
            time_in_force=order.time_in_force,
            sequence=order.sequence,
            queue_position=queue_position
        )
        
        book[order.price].append(order_with_position)
        self._orders[order.order_id] = order_with_position


__all__ = [
    "OrderBookSide",
    "PriceLevel",
    "LimitOrder",
    "OrderBookSnapshot",
    "L2OrderBook",
]
