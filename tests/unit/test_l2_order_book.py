"""
Unit tests for L2 Order Book engine.
"""

import pytest
from decimal import Decimal
from datetime import datetime, timezone

from execution.matching.l2_order_book import (
    L2OrderBook,
    LimitOrder,
    OrderBookSnapshot,
    PriceLevel,
)
from core.contracts.canonical import (
    Instrument,
    AssetClass,
    Currency,
    Side,
    TimeInForce,
)


def test_l2_order_book_initialization():
    """Test L2 order book initialization."""
    instrument = Instrument(
        symbol="AAPL",
        asset_class=AssetClass.EQUITY,
        currency=Currency.USD,
        exchange="NASDAQ"
    )
    
    book = L2OrderBook(instrument, max_depth=10)
    
    assert book.instrument == instrument
    assert book.best_bid is None
    assert book.best_ask is None
    assert book.spread is None
    assert book.mid_price is None


def test_add_limit_order():
    """Test adding limit orders."""
    instrument = Instrument(
        symbol="AAPL",
        asset_class=AssetClass.EQUITY,
        currency=Currency.USD,
        exchange="NASDAQ"
    )
    
    book = L2OrderBook(instrument)
    
    # Add a bid order
    fills, remaining = book.add_limit_order(
        order_id="order1",
        side=Side.BUY,
        price=Decimal("150.00"),
        quantity=Decimal("100"),
        time_in_force=TimeInForce.GTC
    )
    
    assert len(fills) == 0  # No fills yet
    assert remaining is not None
    assert remaining.order_id == "order1"
    assert remaining.quantity == Decimal("100")
    
    # Add an ask order
    fills, remaining = book.add_limit_order(
        order_id="order2",
        side=Side.SELL,
        price=Decimal("151.00"),
        quantity=Decimal("50"),
        time_in_force=TimeInForce.GTC
    )
    
    assert len(fills) == 0  # No cross
    assert remaining is not None
    
    # Check best bid/ask
    assert book.best_bid == Decimal("150.00")
    assert book.best_ask == Decimal("151.00")
    assert book.spread == Decimal("1.00")
    assert book.mid_price == Decimal("150.50")


def test_order_matching():
    """Test order matching logic."""
    instrument = Instrument(
        symbol="AAPL",
        asset_class=AssetClass.EQUITY,
        currency=Currency.USD,
        exchange="NASDAQ"
    )
    
    book = L2OrderBook(instrument)
    
    # Add ask order first
    book.add_limit_order(
        order_id="ask1",
        side=Side.SELL,
        price=Decimal("150.00"),
        quantity=Decimal("100"),
        time_in_force=TimeInForce.GTC
    )
    
    # Add crossing bid order
    fills, remaining = book.add_limit_order(
        order_id="bid1",
        side=Side.BUY,
        price=Decimal("151.00"),
        quantity=Decimal("50"),
        time_in_force=TimeInForce.GTC
    )
    
    # Should fill completely (since bid quantity <= ask quantity)
    assert len(fills) == 1
    assert fills[0][0] == "ask1"  # Matched with ask1
    assert fills[0][1] == Decimal("150.00")  # Fill at ask price
    assert fills[0][2] == Decimal("50")  # Fill quantity
    
    # Bid should be fully filled (no remaining)
    assert remaining is None


def test_queue_position():
    """Test queue position tracking."""
    instrument = Instrument(
        symbol="AAPL",
        asset_class=AssetClass.EQUITY,
        currency=Currency.USD,
        exchange="NASDAQ"
    )
    
    book = L2OrderBook(instrument)
    
    # Add multiple orders at same price level
    book.add_limit_order("order1", Side.BUY, Decimal("150.00"), Decimal("100"))
    book.add_limit_order("order2", Side.BUY, Decimal("150.00"), Decimal("50"))
    book.add_limit_order("order3", Side.BUY, Decimal("150.00"), Decimal("75"))
    
    # Check queue positions
    assert book.get_queue_position("order1") == 0
    assert book.get_queue_position("order2") == 1
    assert book.get_queue_position("order3") == 2


def test_cancel_order():
    """Test order cancellation."""
    instrument = Instrument(
        symbol="AAPL",
        asset_class=AssetClass.EQUITY,
        currency=Currency.USD,
        exchange="NASDAQ"
    )
    
    book = L2OrderBook(instrument)
    
    # Add order
    book.add_limit_order("order1", Side.BUY, Decimal("150.00"), Decimal("100"))
    
    # Cancel order
    result = book.cancel_order("order1")
    assert result is True
    
    # Order should not exist
    assert book.get_order("order1") is None
    assert book.get_queue_position("order1") is None
    
    # Cancel non-existent order
    result = book.cancel_order("order1")
    assert result is False


def test_replace_order():
    """Test order replacement."""
    instrument = Instrument(
        symbol="AAPL",
        asset_class=AssetClass.EQUITY,
        currency=Currency.USD,
        exchange="NASDAQ"
    )
    
    book = L2OrderBook(instrument)
    
    # Add order
    book.add_limit_order("order1", Side.BUY, Decimal("150.00"), Decimal("100"))
    
    # Replace with different price
    fills, remaining = book.replace_order("order1", new_price=Decimal("149.00"))
    
    # Original order should be cancelled
    assert book.get_order("order1") is None
    
    # New order should exist
    assert remaining is not None
    assert remaining.price == Decimal("149.00")


def test_get_snapshot():
    """Test order book snapshot."""
    instrument = Instrument(
        symbol="AAPL",
        asset_class=AssetClass.EQUITY,
        currency=Currency.USD,
        exchange="NASDAQ"
    )
    
    book = L2OrderBook(instrument)
    
    # Add some orders
    book.add_limit_order("bid1", Side.BUY, Decimal("150.00"), Decimal("100"))
    book.add_limit_order("bid2", Side.BUY, Decimal("149.00"), Decimal("50"))
    book.add_limit_order("ask1", Side.SELL, Decimal("151.00"), Decimal("75"))
    book.add_limit_order("ask2", Side.SELL, Decimal("152.00"), Decimal("100"))
    
    # Get snapshot
    snapshot = book.get_snapshot(depth=5)
    
    assert isinstance(snapshot, OrderBookSnapshot)
    assert len(snapshot.bids) == 2
    assert len(snapshot.asks) == 2
    assert snapshot.bids[0].price == Decimal("150.00")  # Best bid
    assert snapshot.asks[0].price == Decimal("151.00")  # Best ask
    assert snapshot.spread == Decimal("1.00")
    assert snapshot.mid_price == Decimal("150.50")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
