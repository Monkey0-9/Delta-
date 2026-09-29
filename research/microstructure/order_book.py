"""Order book data structure for microstructure replay.

Implements price-time priority order book with L2/L3 levels.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional
from collections import defaultdict
import bisect


class Side(str, Enum):
    """Order side."""
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    """Order type."""
    LIMIT = "LIMIT"
    MARKET = "MARKET"
    IOC = "IOC"  # Immediate or Cancel
    FOK = "FOK"  # Fill or Kill


@dataclass(frozen=True, slots=True)
class Order:
    """Order representation."""
    order_id: str
    symbol: str
    side: Side
    order_type: OrderType
    price: float
    quantity: float
    timestamp: float
    exchange: str = "EXCHANGE"

    def __post_init__(self):
        if self.order_type != OrderType.MARKET and self.price <= 0:
            raise ValueError("Price must be positive for non-market orders")
        if self.quantity <= 0:
            raise ValueError("Quantity must be positive")


@dataclass(frozen=True, slots=True)
class PriceLevel:
    """Price level in order book."""
    price: float
    total_quantity: float
    order_count: int
    orders: List[str] = field(default_factory=list)  # order_ids


@dataclass(frozen=True, slots=True)
class Trade:
    """Trade execution."""
    trade_id: str
    symbol: str
    price: float
    quantity: float
    aggressive_order_id: str
    passive_order_id: str
    timestamp: float
    exchange: str = "EXCHANGE"


class OrderBook:
    """Price-time priority order book."""

    def __init__(self, symbol: str):
        self.symbol = symbol
        self.bids: Dict[float, PriceLevel] = {}  # price -> PriceLevel (descending)
        self.asks: Dict[float, PriceLevel] = {}  # price -> PriceLevel (ascending)
        self.orders: Dict[str, Order] = {}  # order_id -> Order
        self.sequence_number: int = 0
        self._bid_prices: List[float] = []  # Sorted bid prices (descending)
        self._ask_prices: List[float] = []  # Sorted ask prices (ascending)

    def add_order(self, order: Order) -> None:
        """Add order to book."""
        self.orders[order.order_id] = order
        self.sequence_number += 1

        if order.side == Side.BUY:
            self._add_to_side(order, self.bids, self._bid_prices, reverse=True)
        else:
            self._add_to_side(order, self.asks, self._ask_prices, reverse=False)

    def _add_to_side(
        self,
        order: Order,
        book: Dict[float, PriceLevel],
        price_list: List[float],
        reverse: bool
    ) -> None:
        """Add order to one side of the book."""
        if order.price in book:
            level = book[order.price]
            new_level = PriceLevel(
                price=level.price,
                total_quantity=level.total_quantity + order.quantity,
                order_count=level.order_count + 1,
                orders=level.orders + [order.order_id]
            )
            book[order.price] = new_level
        else:
            bisect.insort(price_list, order.price)
            book[order.price] = PriceLevel(
                price=order.price,
                total_quantity=order.quantity,
                order_count=1,
                orders=[order.order_id]
            )

    def remove_order(self, order_id: str) -> Optional[Order]:
        """Remove order from book."""
        if order_id not in self.orders:
            return None

        order = self.orders.pop(order_id)
        self.sequence_number += 1

        if order.side == Side.BUY:
            self._remove_from_side(order, self.bids, self._bid_prices)
        else:
            self._remove_from_side(order, self.asks, self._ask_prices)

        return order

    def _remove_from_side(
        self,
        order: Order,
        book: Dict[float, PriceLevel],
        price_list: List[float]
    ) -> None:
        """Remove order from one side of the book."""
        if order.price not in book:
            return

        level = book[order.price]
        if order.order_id in level.orders:
            orders = [o for o in level.orders if o != order.order_id]
            if orders:
                new_level = PriceLevel(
                    price=level.price,
                    total_quantity=level.total_quantity - order.quantity,
                    order_count=level.order_count - 1,
                    orders=orders
                )
                book[order.price] = new_level
            else:
                # Remove price level
                del book[order.price]
                index = bisect.bisect_left(price_list, order.price)
                if index < len(price_list) and price_list[index] == order.price:
                    price_list.pop(index)

    def modify_order(self, order_id: str, new_quantity: float) -> bool:
        """Modify order quantity."""
        if order_id not in self.orders:
            return False

        order = self.orders[order_id]
        old_quantity = order.quantity

        # Remove old order
        self.remove_order(order_id)

        # Add modified order
        modified_order = Order(
            order_id=order.order_id,
            symbol=order.symbol,
            side=order.side,
            order_type=order.order_type,
            price=order.price,
            quantity=new_quantity,
            timestamp=order.timestamp,
            exchange=order.exchange
        )
        self.add_order(modified_order)

        return True

    def get_best_bid(self) -> Optional[float]:
        """Get best bid price."""
        return self._bid_prices[0] if self._bid_prices else None

    def get_best_ask(self) -> Optional[float]:
        """Get best ask price."""
        return self._ask_prices[0] if self._ask_prices else None

    def get_spread(self) -> Optional[float]:
        """Get bid-ask spread."""
        best_bid = self.get_best_bid()
        best_ask = self.get_best_ask()
        if best_bid and best_ask:
            return best_ask - best_bid
        return None

    def get_mid_price(self) -> Optional[float]:
        """Get mid price."""
        best_bid = self.get_best_bid()
        best_ask = self.get_best_ask()
        if best_bid and best_ask:
            return (best_bid + best_ask) / 2.0
        return None

    def get_depth(self, levels: int = 5) -> tuple[List[PriceLevel], List[PriceLevel]]:
        """Get order book depth."""
        bid_levels = [self.bids[p] for p in self._bid_prices[:levels]]
        ask_levels = [self.asks[p] for p in self._ask_prices[:levels]]
        return bid_levels, ask_levels

    def get_l2_snapshot(self) -> Dict:
        """Get L2 snapshot."""
        bid_levels, ask_levels = self.get_depth(10)
        return {
            "symbol": self.symbol,
            "sequence": self.sequence_number,
            "bids": [
                {"price": level.price, "quantity": level.total_quantity}
                for level in bid_levels
            ],
            "asks": [
                {"price": level.price, "quantity": level.total_quantity}
                for level in ask_levels
            ],
            "best_bid": self.get_best_bid(),
            "best_ask": self.get_best_ask(),
            "spread": self.get_spread(),
            "mid": self.get_mid_price()
        }

    def get_imbalance(self) -> Optional[float]:
        """Get order book imbalance."""
        total_bid_qty = sum(level.total_quantity for level in self.bids.values())
        total_ask_qty = sum(level.total_quantity for level in self.asks.values())

        if total_bid_qty + total_ask_qty == 0:
            return None

        return (total_bid_qty - total_ask_qty) / (total_bid_qty + total_ask_qty)


__all__ = [
    "Side",
    "OrderType",
    "Order",
    "PriceLevel",
    "Trade",
    "OrderBook",
]