"""Matching engine for order book simulation.

Implements price-time priority matching with limit, market, IOC, and FOK orders.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple
from enum import Enum
import time

from .order_book import Order, OrderBook, Side, OrderType, Trade, PriceLevel


class MatchAlgorithm(str, Enum):
    """Matching algorithm."""
    PRICE_TIME = "PRICE_TIME"
    PRO_RATA = "PRO_RATA"


@dataclass(frozen=True, slots=True)
class MatchResult:
    """Result of matching attempt."""
    trades: List[Trade] = field(default_factory=list)
    remaining_order: Optional[Order] = None
    fully_filled: bool = False
    rejected: bool = False
    rejection_reason: str = ""


class MatchingEngine:
    """Price-time priority matching engine."""

    def __init__(self, symbol: str, algorithm: MatchAlgorithm = MatchAlgorithm.PRICE_TIME):
        self.symbol = symbol
        self.algorithm = algorithm
        self.order_book = OrderBook(symbol)
        self.trade_counter: int = 0
        self.trades: List[Trade] = []

    def submit_order(self, order: Order) -> MatchResult:
        """Submit order for matching."""
        if order.side == Side.BUY:
            return self._match_buy(order)
        else:
            return self._match_sell(order)

    def _match_buy(self, order: Order) -> MatchResult:
        """Match buy order against asks."""
        trades = []
        remaining_qty = order.quantity

        # Market orders can only trade against existing liquidity
        if order.order_type == OrderType.MARKET and not self.order_book._ask_prices:
            return MatchResult(
                trades=[],
                remaining_order=None,
                fully_filled=False,
                rejected=True,
                rejection_reason="No ask liquidity for market order"
            )

        # Match against asks
        while remaining_qty > 0 and self.order_book._ask_prices:
            best_ask_price = self.order_book._ask_prices[0]

            # Stop if limit order price is below best ask
            if order.order_type == OrderType.LIMIT and order.price < best_ask_price:
                break

            # Get price level
            ask_level = self.order_book.asks[best_ask_price]

            # Match against orders at this price level
            for order_id in list(ask_level.orders):
                if remaining_qty <= 0:
                    break

                passive_order = self.order_book.orders.get(order_id)
                if not passive_order:
                    continue

                match_qty = min(remaining_qty, passive_order.quantity)
                trade_price = best_ask_price

                # Create trade
                trade = Trade(
                    trade_id=f"T-{self.trade_counter}",
                    symbol=self.symbol,
                    price=trade_price,
                    quantity=match_qty,
                    aggressive_order_id=order.order_id,
                    passive_order_id=order_id,
                    timestamp=time.time()
                )
                trades.append(trade)
                self.trades.append(trade)
                self.trade_counter += 1

                # Update quantities
                remaining_qty -= match_qty

                # Remove or modify passive order
                if passive_order.quantity == match_qty:
                    self.order_book.remove_order(order_id)
                else:
                    self.order_book.modify_order(order_id, passive_order.quantity - match_qty)

            # Remove empty price level
            current_level = self.order_book.asks.get(best_ask_price)
            if not current_level or not current_level.orders:
                if best_ask_price in self.order_book.asks:
                    del self.order_book.asks[best_ask_price]
                if self.order_book._ask_prices and self.order_book._ask_prices[0] == best_ask_price:
                    self.order_book._ask_prices.pop(0)

        # Handle remaining quantity
        if remaining_qty > 0:
            if order.order_type == OrderType.IOC:
                # Cancel remaining
                return MatchResult(
                    trades=trades,
                    remaining_order=None,
                    fully_filled=False,
                    rejected=False
                )
            elif order.order_type == OrderType.FOK:
                # Reject entire order if not fully filled
                return MatchResult(
                    trades=[],
                    remaining_order=None,
                    fully_filled=False,
                    rejected=True,
                    rejection_reason="FOK order not fully filled"
                )
            else:
                # Add remaining to book
                remaining_order = Order(
                    order_id=order.order_id,
                    symbol=order.symbol,
                    side=order.side,
                    order_type=order.order_type,
                    price=order.price,
                    quantity=remaining_qty,
                    timestamp=order.timestamp,
                    exchange=order.exchange
                )
                self.order_book.add_order(remaining_order)
                return MatchResult(
                    trades=trades,
                    remaining_order=remaining_order,
                    fully_filled=False,
                    rejected=False
                )

        return MatchResult(
            trades=trades,
            remaining_order=None,
            fully_filled=True,
            rejected=False
        )

    def _match_sell(self, order: Order) -> MatchResult:
        """Match sell order against bids."""
        trades = []
        remaining_qty = order.quantity

        # Market orders can only trade against existing liquidity
        if order.order_type == OrderType.MARKET and not self.order_book._bid_prices:
            return MatchResult(
                trades=[],
                remaining_order=None,
                fully_filled=False,
                rejected=True,
                rejection_reason="No bid liquidity for market order"
            )

        # Match against bids
        while remaining_qty > 0 and self.order_book._bid_prices:
            best_bid_price = self.order_book._bid_prices[0]

            # Stop if limit order price is above best bid
            if order.order_type == OrderType.LIMIT and order.price > best_bid_price:
                break

            # Get price level
            bid_level = self.order_book.bids[best_bid_price]

            # Match against orders at this price level
            for order_id in list(bid_level.orders):
                if remaining_qty <= 0:
                    break

                passive_order = self.order_book.orders.get(order_id)
                if not passive_order:
                    continue

                match_qty = min(remaining_qty, passive_order.quantity)
                trade_price = best_bid_price

                # Create trade
                trade = Trade(
                    trade_id=f"T-{self.trade_counter}",
                    symbol=self.symbol,
                    price=trade_price,
                    quantity=match_qty,
                    aggressive_order_id=order.order_id,
                    passive_order_id=order_id,
                    timestamp=time.time()
                )
                trades.append(trade)
                self.trades.append(trade)
                self.trade_counter += 1

                # Update quantities
                remaining_qty -= match_qty

                # Remove or modify passive order
                if passive_order.quantity == match_qty:
                    self.order_book.remove_order(order_id)
                else:
                    self.order_book.modify_order(order_id, passive_order.quantity - match_qty)

            # Remove empty price level
            current_level = self.order_book.bids.get(best_bid_price)
            if not current_level or not current_level.orders:
                if best_bid_price in self.order_book.bids:
                    del self.order_book.bids[best_bid_price]
                if self.order_book._bid_prices and self.order_book._bid_prices[0] == best_bid_price:
                    self.order_book._bid_prices.pop(0)

        # Handle remaining quantity
        if remaining_qty > 0:
            if order.order_type == OrderType.IOC:
                # Cancel remaining
                return MatchResult(
                    trades=trades,
                    remaining_order=None,
                    fully_filled=False,
                    rejected=False
                )
            elif order.order_type == OrderType.FOK:
                # Reject entire order if not fully filled
                return MatchResult(
                    trades=[],
                    remaining_order=None,
                    fully_filled=False,
                    rejected=True,
                    rejection_reason="FOK order not fully filled"
                )
            else:
                # Add remaining to book
                remaining_order = Order(
                    order_id=order.order_id,
                    symbol=order.symbol,
                    side=order.side,
                    order_type=order.order_type,
                    price=order.price,
                    quantity=remaining_qty,
                    timestamp=order.timestamp,
                    exchange=order.exchange
                )
                self.order_book.add_order(remaining_order)
                return MatchResult(
                    trades=trades,
                    remaining_order=remaining_order,
                    fully_filled=False,
                    rejected=False
                )

        return MatchResult(
            trades=trades,
            remaining_order=None,
            fully_filled=True,
            rejected=False
        )

    def cancel_order(self, order_id: str) -> bool:
        """Cancel order."""
        return self.order_book.remove_order(order_id) is not None

    def get_order_book(self) -> OrderBook:
        """Get current order book state."""
        return self.order_book

    def get_trades(self) -> List[Trade]:
        """Get all trades."""
        return self.trades.copy()

    def reset(self) -> None:
        """Reset matching engine."""
        self.order_book = OrderBook(self.symbol)
        self.trade_counter = 0
        self.trades = []


__all__ = [
    "MatchAlgorithm",
    "MatchResult",
    "MatchingEngine",
]