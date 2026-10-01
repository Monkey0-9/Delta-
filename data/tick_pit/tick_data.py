"""
Tick-level data structures for institutional market data.

This defines the fundamental data contracts for:
- Quotes (bid/ask updates)
- Trades (execution updates)
- Order book updates (L2/L3 depth changes)
- Cross-tick aggregation
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional, Union
import uuid


class TickType(Enum):
    """Tick data type enumeration."""
    QUOTE = "QUOTE"
    TRADE = "TRADE"
    ORDER_BOOK_UPDATE = "ORDER_BOOK_UPDATE"
    OPENING = "OPENING"
    CLOSING = "CLOSING"
    AUCTION = "AUCTION"
    SETTLEMENT = "SETTLEMENT"


@dataclass(frozen=True, slots=True)
class Quote:
    """
    Quote (L1) data structure.
    """
    symbol: str
    exchange: str
    bid_price: float
    ask_price: float
    bid_size: float
    ask_size: float
    bid_exchange: str = ""
    ask_exchange: str = ""
    quote_condition: str = "REGULAR"
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    sequence_number: int = 0
    
    @property
    def spread(self) -> float:
        """Calculate spread."""
        return self.ask_price - self.bid_price
    
    @property
    def mid_price(self) -> float:
        """Calculate mid price."""
        return (self.bid_price + self.ask_price) / 2.0
    
    @property
    def spread_bps(self) -> float:
        """Calculate spread in basis points."""
        if self.mid_price == 0:
            return 0.0
        return (self.spread / self.mid_price) * 10000


@dataclass(frozen=True, slots=True)
class Trade:
    """
    Trade data structure.
    """
    symbol: str
    exchange: str
    price: float
    quantity: float
    trade_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    trade_condition: str = "REGULAR"
    buyer: str = ""
    seller: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    sequence_number: int = 0
    
    @property
    def notional(self) -> float:
        """Calculate trade notional."""
        return self.price * self.quantity


@dataclass(frozen=True, slots=True)
class OrderBookLevel:
    """
    Single order book level (L2/L3).
    """
    price: float
    size: float
    num_orders: int = 1
    exchange: str = ""
    
    def __add__(self, other: 'OrderBookLevel') -> 'OrderBookLevel':
        """Aggregate order book levels."""
        if self.price != other.price:
            raise ValueError("Cannot aggregate levels with different prices")
        
        return OrderBookLevel(
            price=self.price,
            size=self.size + other.size,
            num_orders=self.num_orders + other.num_orders,
            exchange=self.exchange
        )


@dataclass(frozen=True, slots=True)
class OrderBookUpdate:
    """
    Order book update (L2/L3) data structure.
    """
    symbol: str
    exchange: str
    side: str  # "BID" or "ASK"
    levels: List[OrderBookLevel]
    update_type: str = "SNAPSHOT"  # SNAPSHOT, INCREMENTAL, DELETE
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    sequence_number: int = 0
    
    @property
    def total_size(self) -> float:
        """Calculate total size at all levels."""
        return sum(level.size for level in self.levels)
    
    @property
    def weighted_average_price(self) -> float:
        """Calculate volume-weighted average price."""
        total_size = self.total_size
        if total_size == 0:
            return 0.0
        
        weighted_sum = sum(level.price * level.size for level in self.levels)
        return weighted_sum / total_size


@dataclass(frozen=True, slots=True)
class TickData:
    """
    Unified tick data structure.
    """
    tick_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    tick_type: TickType = TickType.QUOTE
    data: Union[Quote, Trade, OrderBookUpdate] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    exchange: str = ""
    symbol: str = ""
    sequence_number: int = 0
    
    @classmethod
    def from_quote(cls, quote: Quote) -> 'TickData':
        """Create TickData from Quote."""
        return cls(
            tick_type=TickType.QUOTE,
            data=quote,
            timestamp=quote.timestamp,
            exchange=quote.exchange,
            symbol=quote.symbol,
            sequence_number=quote.sequence_number
        )
    
    @classmethod
    def from_trade(cls, trade: Trade) -> 'TickData':
        """Create TickData from Trade."""
        return cls(
            tick_type=TickType.TRADE,
            data=trade,
            timestamp=trade.timestamp,
            exchange=trade.exchange,
            symbol=trade.symbol,
            sequence_number=trade.sequence_number
        )
    
    @classmethod
    def from_order_book_update(cls, update: OrderBookUpdate) -> 'TickData':
        """Create TickData from OrderBookUpdate."""
        return cls(
            tick_type=TickType.ORDER_BOOK_UPDATE,
            data=update,
            timestamp=update.timestamp,
            exchange=update.exchange,
            symbol=update.symbol,
            sequence_number=update.sequence_number
        )
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        result = {
            "tick_id": self.tick_id,
            "tick_type": self.tick_type.value,
            "timestamp": self.timestamp.isoformat(),
            "exchange": self.exchange,
            "symbol": self.symbol,
            "sequence_number": self.sequence_number
        }
        
        if self.data is not None:
            if isinstance(self.data, Quote):
                result["quote"] = {
                    "bid_price": self.data.bid_price,
                    "ask_price": self.data.ask_price,
                    "bid_size": self.data.bid_size,
                    "ask_size": self.data.ask_size,
                    "spread": self.data.spread,
                    "mid_price": self.data.mid_price,
                    "spread_bps": self.data.spread_bps
                }
            elif isinstance(self.data, Trade):
                result["trade"] = {
                    "price": self.data.price,
                    "quantity": self.data.quantity,
                    "notional": self.data.notional,
                    "trade_id": self.data.trade_id
                }
            elif isinstance(self.data, OrderBookUpdate):
                result["order_book"] = {
                    "side": self.data.side,
                    "total_size": self.data.total_size,
                    "weighted_avg_price": self.data.weighted_average_price,
                    "num_levels": len(self.data.levels)
                }
        
        return result


class TickAggregator:
    """
    Aggregates tick data into different time intervals.
    
    Supports:
    - Tick aggregation to OHLCV bars
    - Volume-weighted average price (VWAP)
    - Time-bar aggregation
    - Tick-bar aggregation
    """
    
    def __init__(self, symbol: str):
        self.symbol = symbol
        self.ticks: List[TickData] = []
        self.aggregation_window: int = 1000  # Default 1000 ticks
    
    def add_tick(self, tick: TickData) -> None:
        """Add tick to aggregator."""
        self.ticks.append(tick)
    
    def aggregate_to_ohlcv(self, start_time: datetime, end_time: datetime) -> Dict:
        """
        Aggregate ticks to OHLCV bar.
        
        Args:
            start_time: Start of aggregation window
            end_time: End of aggregation window
            
        Returns:
            Dictionary with OHLCV data
        """
        # Filter ticks in time window
        window_ticks = [
            tick for tick in self.ticks
            if start_time <= tick.timestamp <= end_time
        ]
        
        if not window_ticks:
            return {
                "symbol": self.symbol,
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "open": None,
                "high": None,
                "low": None,
                "close": None,
                "volume": 0.0,
                "num_ticks": 0
            }
        
        # Extract prices from quotes and trades
        prices = []
        volumes = []
        
        for tick in window_ticks:
            if isinstance(tick.data, Quote):
                prices.append(tick.data.mid_price)
            elif isinstance(tick.data, Trade):
                prices.append(tick.data.price)
                volumes.append(tick.data.quantity)
        
        if not prices:
            return {
                "symbol": self.symbol,
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "open": None,
                "high": None,
                "low": None,
                "close": None,
                "volume": 0.0,
                "num_ticks": len(window_ticks)
            }
        
        return {
            "symbol": self.symbol,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "open": prices[0],
            "high": max(prices),
            "low": min(prices),
            "close": prices[-1],
            "volume": sum(volumes),
            "num_ticks": len(window_ticks)
        }
    
    def calculate_vwap(self, start_time: datetime, end_time: datetime) -> float:
        """
        Calculate volume-weighted average price.
        
        Args:
            start_time: Start of aggregation window
            end_time: End of aggregation window
            
        Returns:
            VWAP price
        """
        # Filter ticks in time window
        window_ticks = [
            tick for tick in self.ticks
            if start_time <= tick.timestamp <= end_time
        ]
        
        # Extract trades only
        trades = [
            tick.data for tick in window_ticks
            if isinstance(tick.data, Trade)
        ]
        
        if not trades:
            return 0.0
        
        total_notional = sum(trade.price * trade.quantity for trade in trades)
        total_volume = sum(trade.quantity for trade in trades)
        
        return total_notional / total_volume if total_volume > 0 else 0.0
    
    def aggregate_tick_bars(self, tick_count: int) -> List[Dict]:
        """
        Aggregate by tick count (tick bars).
        
        Args:
            tick_count: Number of ticks per bar
            
        Returns:
            List of OHLCV bars
        """
        bars = []
        
        for i in range(0, len(self.ticks), tick_count):
            window_ticks = self.ticks[i:i + tick_count]
            
            if not window_ticks:
                continue
            
            start_time = window_ticks[0].timestamp
            end_time = window_ticks[-1].timestamp
            
            bar = self.aggregate_to_ohlcv(start_time, end_time)
            bars.append(bar)
        
        return bars
    
    def clear(self) -> None:
        """Clear all ticks."""
        self.ticks.clear()


__all__ = [
    "TickType",
    "Quote",
    "Trade",
    "OrderBookLevel",
    "OrderBookUpdate",
    "TickData",
    "TickAggregator"
]