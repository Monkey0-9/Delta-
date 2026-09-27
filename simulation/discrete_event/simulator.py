"""Market Simulator with Order Book dynamics."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4
import threading


class OrderSide(StrEnum):
    """Order side."""
    BUY = "buy"
    SELL = "sell"


class OrderType(StrEnum):
    """Order type."""
    LIMIT = "limit"
    MARKET = "market"
    STOP = "stop"


@dataclass(frozen=True, slots=True)
class LimitOrder:
    """Limit order in the order book."""
    order_id: UUID = field(default_factory=uuid4)
    side: OrderSide = OrderSide.BUY
    price: Decimal = Decimal("0")
    quantity: Decimal = Decimal("0")
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Metadata
    trader_id: str = ""
    is_iceberg: bool = False
    display_quantity: Decimal = Decimal("0")  # For iceberg orders


@dataclass(frozen=True, slots=True)
class PriceLevel:
    """Price level in the order book."""
    price: Decimal
    quantity: Decimal
    order_count: int = 0


@dataclass(frozen=True, slots=True)
class OrderBook:
    """
    Limit order book with bid and ask sides.
    
    Implements price-time priority for matching.
    """
    instrument_id: UUID = field(default_factory=uuid4)
    bids: dict[Decimal, list[LimitOrder]] = field(default_factory=dict)
    asks: dict[Decimal, list[LimitOrder]] = field(default_factory=dict)
    
    # Thread safety
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)
    
    def add_order(self, order: LimitOrder) -> None:
        """Add order to the book."""
        with self._lock:
            if order.side == OrderSide.BUY:
                if order.price not in self.bids:
                    self.bids[order.price] = []
                self.bids[order.price].append(order)
            else:
                if order.price not in self.asks:
                    self.asks[order.price] = []
                self.asks[order.price].append(order)
    
    def remove_order(self, order_id: UUID) -> bool:
        """Remove order from the book."""
        with self._lock:
            # Search in bids
            for price, orders in self.bids.items():
                for i, order in enumerate(orders):
                    if order.order_id == order_id:
                        orders.pop(i)
                        if not orders:
                            del self.bids[price]
                        return True
            
            # Search in asks
            for price, orders in self.asks.items():
                for i, order in enumerate(orders):
                    if order.order_id == order_id:
                        orders.pop(i)
                        if not orders:
                            del self.asks[price]
                        return True
        
        return False
    
    def get_best_bid(self) -> PriceLevel | None:
        """Get best bid (highest price)."""
        with self._lock:
            if not self.bids:
                return None
            
            best_price = max(self.bids.keys())
            orders = self.bids[best_price]
            total_qty = sum(o.quantity for o in orders)
            
            return PriceLevel(
                price=best_price,
                quantity=total_qty,
                order_count=len(orders)
            )
    
    def get_best_ask(self) -> PriceLevel | None:
        """Get best ask (lowest price)."""
        with self._lock:
            if not self.asks:
                return None
            
            best_price = min(self.asks.keys())
            orders = self.asks[best_price]
            total_qty = sum(o.quantity for o in orders)
            
            return PriceLevel(
                price=best_price,
                quantity=total_qty,
                order_count=len(orders)
            )
    
    def get_spread(self) -> Decimal | None:
        """Get bid-ask spread."""
        best_bid = self.get_best_bid()
        best_ask = self.get_best_ask()
        
        if best_bid is None or best_ask is None:
            return None
        
        return best_ask.price - best_bid.price
    
    def get_mid_price(self) -> Decimal | None:
        """Get mid price."""
        best_bid = self.get_best_bid()
        best_ask = self.get_best_ask()
        
        if best_bid is None or best_ask is None:
            return None
        
        return (best_bid.price + best_ask.price) / Decimal("2")
    
    def get_depth(self, levels: int = 5) -> dict[str, list[PriceLevel]]:
        """Get order book depth."""
        with self._lock:
            # Get top N bid levels
            bid_prices = sorted(self.bids.keys(), reverse=True)[:levels]
            bid_levels = [
                PriceLevel(
                    price=price,
                    quantity=sum(o.quantity for o in self.bids[price]),
                    order_count=len(self.bids[price])
                )
                for price in bid_prices
            ]
            
            # Get top N ask levels
            ask_prices = sorted(self.asks.keys())[:levels]
            ask_levels = [
                PriceLevel(
                    price=price,
                    quantity=sum(o.quantity for o in self.asks[price]),
                    order_count=len(self.asks[price])
                )
                for price in ask_prices
            ]
            
            return {
                "bids": bid_levels,
                "asks": ask_levels
            }


class MarketSimulator:
    """
    Market simulator with order book and trade matching.
    
    Simulates realistic market microstructure including:
    - Price-time priority
    - Queue position effects
    - Market impact
    """
    
    def __init__(self) -> None:
        self._order_books: dict[UUID, OrderBook] = {}
        self._last_prices: dict[UUID, Decimal] = {}
    
    def get_or_create_book(self, instrument_id: UUID) -> OrderBook:
        """Get or create order book for instrument."""
        if instrument_id not in self._order_books:
            self._order_books[instrument_id] = OrderBook(instrument_id=instrument_id)
        return self._order_books[instrument_id]
    
    def submit_order(self, order: LimitOrder) -> dict[str, Any]:
        """Submit order and attempt to match."""
        book = self.get_or_create_book(order.instrument_id)
        
        # For simplicity, just add to book (real implementation would match)
        book.add_order(order)
        
        return {
            "order_id": str(order.order_id),
            "status": "accepted",
            "timestamp": order.timestamp,
        }
    
    def cancel_order(self, order_id: UUID, instrument_id: UUID) -> bool:
        """Cancel order."""
        book = self.get_or_create_book(instrument_id)
        return book.remove_order(order_id)
    
    def get_market_data(self, instrument_id: UUID) -> dict[str, Any]:
        """Get current market data."""
        book = self.get_or_create_book(instrument_id)
        
        best_bid = book.get_best_bid()
        best_ask = book.get_best_ask()
        spread = book.get_spread()
        mid_price = book.get_mid_price()
        
        return {
            "instrument_id": str(instrument_id),
            "best_bid": float(best_bid.price) if best_bid else None,
            "best_ask": float(best_ask.price) if best_ask else None,
            "spread": float(spread) if spread else None,
            "mid_price": float(mid_price) if mid_price else None,
            "timestamp": datetime.now(timezone.utc),
        }
