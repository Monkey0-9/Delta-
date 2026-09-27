"""
L2/L3 Order Book with price-time priority and queue position tracking.

This implements institutional-grade order book mechanics:
- Price-time priority (FIFO)
- L2 (best bid/ask with depth) and L3 (full depth) support
- Queue position tracking
- Order cancellation and modification
- Volume-weighted average price calculation
- Spread and imbalance metrics
"""
from __future__ import annotations

import bisect
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional, Tuple
import heapq


__all__ = [
    "OrderSide",
    "LimitOrder",
    "MarketOrder",
    "OrderBookLevel",
    "OrderBook"
]


class OrderSide(Enum):
    """Order side enumeration."""
    BUY = "BUY"
    SELL = "SELL"


@dataclass(frozen=True, slots=True)
class LimitOrder:
    """
    Limit order with complete institutional fields.
    """
    order_id: str
    side: OrderSide
    price: float
    quantity: float
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    exchange: str = "SIM"
    participant: str = "DEFAULT"
    order_type: str = "LIMIT"
    
    def __lt__(self, other: LimitOrder) -> bool:
        """Price-time priority comparison."""
        if self.side == OrderSide.BUY:
            # Higher price first for buys
            if self.price != other.price:
                return self.price > other.price
            # Earlier timestamp first for same price
            return self.timestamp < other.timestamp
        else:
            # Lower price first for sells
            if self.price != other.price:
                return self.price < other.price
            # Earlier timestamp first for same price
            return self.timestamp < other.timestamp


@dataclass(frozen=True, slots=True)
class MarketOrder:
    """
    Market order with complete institutional fields.
    """
    order_id: str
    side: OrderSide
    quantity: float
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    exchange: str = "SIM"
    participant: str = "DEFAULT"
    order_type: str = "MARKET"


@dataclass
class OrderBookLevel:
    """
    Single price level in the order book.
    """
    price: float
    total_quantity: float
    orders: List[LimitOrder] = field(default_factory=list)
    
    def add_order(self, order: LimitOrder) -> None:
        """Add order to this price level."""
        bisect.insort(self.orders, order)
        self.total_quantity += order.quantity
    
    def remove_order(self, order: LimitOrder) -> bool:
        """Remove order from this price level."""
        try:
            index = self.orders.index(order)
            removed_order = self.orders.pop(index)
            self.total_quantity -= removed_order.quantity
            return True
        except ValueError:
            return False
    
    def reduce_quantity(self, order_id: str, reduction: float) -> bool:
        """Reduce quantity of specific order."""
        for order in self.orders:
            if order.order_id == order_id:
                if reduction >= order.quantity:
                    return self.remove_order(order)
                else:
                    # Create new order with reduced quantity
                    new_order = LimitOrder(
                        order_id=order.order_id,
                        side=order.side,
                        price=order.price,
                        quantity=order.quantity - reduction,
                        timestamp=order.timestamp,
                        exchange=order.exchange,
                        participant=order.participant,
                        order_type=order.order_type
                    )
                    self.remove_order(order)
                    self.add_order(new_order)
                    self.total_quantity -= reduction
                    return True
        return False
    
    def get_queue_position(self, order_id: str) -> int:
        """Get queue position (0-indexed) for order."""
        for i, order in enumerate(self.orders):
            if order.order_id == order_id:
                return i
        return -1


class OrderBook:
    """
    L2/L3 Order Book with price-time priority and queue position tracking.
    
    Supports:
    - L2 (best bid/ask with depth)
    - L3 (full depth with individual orders)
    - Queue position calculation
    - Spread and imbalance metrics
    - Order modification and cancellation
    """
    
    def __init__(self, symbol: str, exchange: str = "SIM"):
        self.symbol = symbol
        self.exchange = exchange
        self.bids: Dict[float, OrderBookLevel] = {}
        self.asks: Dict[float, OrderBookLevel] = {}
        self.bid_prices: List[float] = []  # Sorted descending
        self.ask_prices: List[float] = []  # Sorted ascending
        self.last_update: datetime = datetime.now(timezone.utc)
    
    def add_limit_order(self, order: LimitOrder) -> bool:
        """Add limit order to the book."""
        self.last_update = datetime.now(timezone.utc)
        
        if order.side == OrderSide.BUY:
            level = self.bids.get(order.price)
            if level is None:
                level = OrderBookLevel(price=order.price, total_quantity=0.0)
                self.bids[order.price] = level
                bisect.insort(self.bid_prices, order.price)
                # Keep bids sorted descending
                self.bid_prices.sort(reverse=True)
            level.add_order(order)
        else:
            level = self.asks.get(order.price)
            if level is None:
                level = OrderBookLevel(price=order.price, total_quantity=0.0)
                self.asks[order.price] = level
                bisect.insort(self.ask_prices, order.price)
            level.add_order(order)
        
        return True
    
    def cancel_order(self, order_id: str, side: OrderSide, price: float) -> bool:
        """Cancel order from the book."""
        self.last_update = datetime.now(timezone.utc)
        
        if side == OrderSide.BUY:
            level = self.bids.get(price)
            if level is None:
                return False
            # Find and remove order
            for order in level.orders[:]:
                if order.order_id == order_id:
                    level.remove_order(order)
                    if level.total_quantity <= 0:
                        del self.bids[price]
                        self.bid_prices.remove(price)
                    return True
        else:
            level = self.asks.get(price)
            if level is None:
                return False
            for order in level.orders[:]:
                if order.order_id == order_id:
                    level.remove_order(order)
                    if level.total_quantity <= 0:
                        del self.asks[price]
                        self.ask_prices.remove(price)
                    return True
        
        return False
    
    def modify_order(self, order_id: str, side: OrderSide, old_price: float, 
                    new_price: float, new_quantity: float) -> bool:
        """Modify order price and/or quantity."""
        # Cancel old order
        if not self.cancel_order(order_id, side, old_price):
            return False
        
        # Add new order with same timestamp
        # Find original order timestamp
        original_timestamp = None
        if side == OrderSide.BUY:
            for level in self.bids.values():
                for order in level.orders:
                    if order.order_id == order_id:
                        original_timestamp = order.timestamp
                        break
        else:
            for level in self.asks.values():
                for order in level.orders:
                    if order.order_id == order_id:
                        original_timestamp = order.timestamp
                        break
        
        if original_timestamp is None:
            return False
        
        # Create new order
        new_order = LimitOrder(
            order_id=order_id,
            side=side,
            price=new_price,
            quantity=new_quantity,
            timestamp=original_timestamp,
            exchange=self.exchange
        )
        
        return self.add_limit_order(new_order)
    
    def get_best_bid(self) -> Tuple[float, float]:
        """Get best bid (price, quantity)."""
        if not self.bid_prices:
            return (0.0, 0.0)
        best_price = self.bid_prices[0]
        level = self.bids[best_price]
        return (best_price, level.total_quantity)
    
    def get_best_ask(self) -> Tuple[float, float]:
        """Get best ask (price, quantity)."""
        if not self.ask_prices:
            return (0.0, 0.0)
        best_price = self.ask_prices[0]
        level = self.asks[best_price]
        return (best_price, level.total_quantity)
    
    def get_spread(self) -> float:
        """Get current spread."""
        best_bid, _ = self.get_best_bid()
        best_ask, _ = self.get_best_ask()
        if best_bid == 0.0 or best_ask == 0.0:
            return 0.0
        return best_ask - best_bid
    
    def get_mid_price(self) -> float:
        """Get mid price."""
        best_bid, _ = self.get_best_bid()
        best_ask, _ = self.get_best_ask()
        if best_bid == 0.0 or best_ask == 0.0:
            return 0.0
        return (best_bid + best_ask) / 2.0
    
    def get_vwap(self, side: OrderSide, depth: int = 5) -> float:
        """Calculate volume-weighted average price for given depth."""
        if side == OrderSide.BUY:
            prices = self.bid_prices[:depth]
        else:
            prices = self.ask_prices[:depth]
        
        if not prices:
            return 0.0
        
        total_value = 0.0
        total_volume = 0.0
        
        for price in prices:
            if side == OrderSide.BUY:
                level = self.bids[price]
            else:
                level = self.asks[price]
            
            total_value += price * level.total_quantity
            total_volume += level.total_quantity
        
        return total_value / total_volume if total_volume > 0 else 0.0
    
    def get_order_imbalance(self, depth: int = 5) -> float:
        """Calculate order imbalance ratio (bid volume / ask volume)."""
        bid_volume = sum(
            self.bids[price].total_quantity 
            for price in self.bid_prices[:depth]
        )
        ask_volume = sum(
            self.asks[price].total_quantity 
            for price in self.ask_prices[:depth]
        )
        
        if ask_volume == 0.0:
            return 1.0 if bid_volume > 0 else 0.0
        
        return bid_volume / (bid_volume + ask_volume)
    
    def get_queue_position(self, order_id: str, side: OrderSide, price: float) -> int:
        """Get queue position for order."""
        if side == OrderSide.BUY:
            level = self.bids.get(price)
        else:
            level = self.asks.get(price)
        
        if level is None:
            return -1
        
        return level.get_queue_position(order_id)
    
    def get_l2_snapshot(self, depth: int = 10) -> Dict:
        """Get L2 snapshot (best bid/ask with depth)."""
        return {
            "symbol": self.symbol,
            "exchange": self.exchange,
            "timestamp": self.last_update.isoformat(),
            "bids": [
                {
                    "price": price,
                    "quantity": self.bids[price].total_quantity,
                    "num_orders": len(self.bids[price].orders)
                }
                for price in self.bid_prices[:depth]
            ],
            "asks": [
                {
                    "price": price,
                    "quantity": self.asks[price].total_quantity,
                    "num_orders": len(self.asks[price].orders)
                }
                for price in self.ask_prices[:depth]
            ],
            "spread": self.get_spread(),
            "mid": self.get_mid_price(),
            "imbalance": self.get_order_imbalance(depth)
        }
    
    def get_l3_snapshot(self, depth: int = 5) -> Dict:
        """Get L3 snapshot (full depth with individual orders)."""
        l3_snapshot = self.get_l2_snapshot(depth)
        
        # Add individual order information
        l3_snapshot["bid_orders"] = [
            [
                {
                    "order_id": order.order_id,
                    "quantity": order.quantity,
                    "timestamp": order.timestamp.isoformat(),
                    "participant": order.participant,
                    "queue_position": i
                }
                for i, order in enumerate(self.bids[price].orders[:depth])
            ]
            for price in self.bid_prices[:depth]
        ]
        
        l3_snapshot["ask_orders"] = [
            [
                {
                    "order_id": order.order_id,
                    "quantity": order.quantity,
                    "timestamp": order.timestamp.isoformat(),
                    "participant": order.participant,
                    "queue_position": i
                }
                for i, order in enumerate(self.asks[price].orders[:depth])
            ]
            for price in self.ask_prices[:depth]
        ]
        
        return l3_snapshot
    
    def get_total_bid_volume(self) -> float:
        """Get total bid volume in book."""
        return sum(level.total_quantity for level in self.bids.values())
    
    def get_total_ask_volume(self) -> float:
        """Get total ask volume in book."""
        return sum(level.total_quantity for level in self.asks.values())
    
    def get_book_depth(self) -> Tuple[int, int]:
        """Get number of price levels on each side."""
        return (len(self.bid_prices), len(self.ask_prices))
    
    def clear_book(self) -> None:
        """Clear all orders from the book."""
        self.bids.clear()
        self.asks.clear()
        self.bid_prices.clear()
        self.ask_prices.clear()
        self.last_update = datetime.now(timezone.utc)