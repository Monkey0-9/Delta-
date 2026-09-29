"""Tests for microstructure replay engine."""
import pytest
import time

from research.microstructure import (
    OrderBook,
    Order,
    Trade,
    Side,
    OrderType,
    MatchingEngine,
    OrderBookReplay,
    EventType,
    OrderBookEvent,
    ReplayConfig,
)


class TestOrderBook:
    """Test order book implementation."""

    def test_add_limit_order(self):
        """Test adding limit orders."""
        book = OrderBook("AAPL")

        order = Order(
            order_id="O1",
            symbol="AAPL",
            side=Side.BUY,
            order_type=OrderType.LIMIT,
            price=150.0,
            quantity=100.0,
            timestamp=time.time()
        )

        book.add_order(order)

        assert book.get_best_bid() == 150.0
        assert len(book.bids) == 1
        assert "O1" in book.orders

    def test_remove_order(self):
        """Test removing orders."""
        book = OrderBook("AAPL")

        order = Order(
            order_id="O1",
            symbol="AAPL",
            side=Side.BUY,
            order_type=OrderType.LIMIT,
            price=150.0,
            quantity=100.0,
            timestamp=time.time()
        )

        book.add_order(order)
        removed = book.remove_order("O1")

        assert removed is not None
        assert removed.order_id == "O1"
        assert book.get_best_bid() is None

    def test_spread_calculation(self):
        """Test spread calculation."""
        book = OrderBook("AAPL")

        bid_order = Order(
            order_id="B1",
            symbol="AAPL",
            side=Side.BUY,
            order_type=OrderType.LIMIT,
            price=149.0,
            quantity=100.0,
            timestamp=time.time()
        )

        ask_order = Order(
            order_id="A1",
            symbol="AAPL",
            side=Side.SELL,
            order_type=OrderType.LIMIT,
            price=151.0,
            quantity=100.0,
            timestamp=time.time()
        )

        book.add_order(bid_order)
        book.add_order(ask_order)

        assert book.get_spread() == 2.0
        assert book.get_mid_price() == 150.0

    def test_depth_levels(self):
        """Test getting depth levels."""
        book = OrderBook("AAPL")

        for i in range(5):
            bid_order = Order(
                order_id=f"B{i}",
                symbol="AAPL",
                side=Side.BUY,
                order_type=OrderType.LIMIT,
                price=150.0 - i,
                quantity=100.0,
                timestamp=time.time()
            )
            book.add_order(bid_order)

        bids, asks = book.get_depth(3)
        assert len(bids) == 3
        assert bids[0].price == 150.0


class TestMatchingEngine:
    """Test matching engine."""

    def test_limit_order_match(self):
        """Test limit order matching."""
        engine = MatchingEngine("AAPL")

        # Add sell order
        ask_order = Order(
            order_id="A1",
            symbol="AAPL",
            side=Side.SELL,
            order_type=OrderType.LIMIT,
            price=151.0,
            quantity=100.0,
            timestamp=time.time()
        )
        engine.submit_order(ask_order)

        # Submit buy order that should match
        buy_order = Order(
            order_id="B1",
            symbol="AAPL",
            side=Side.BUY,
            order_type=OrderType.LIMIT,
            price=152.0,
            quantity=50.0,
            timestamp=time.time()
        )
        result = engine.submit_order(buy_order)

        assert result.fully_filled
        assert len(result.trades) == 1
        assert result.trades[0].quantity == 50.0

    def test_market_order_match(self):
        """Test market order matching."""
        engine = MatchingEngine("AAPL")

        # Add sell order
        ask_order = Order(
            order_id="A1",
            symbol="AAPL",
            side=Side.SELL,
            order_type=OrderType.LIMIT,
            price=151.0,
            quantity=100.0,
            timestamp=time.time()
        )
        engine.submit_order(ask_order)

        # Submit market buy order
        market_order = Order(
            order_id="M1",
            symbol="AAPL",
            side=Side.BUY,
            order_type=OrderType.MARKET,
            price=0.0,  # Market orders ignore price
            quantity=50.0,
            timestamp=time.time()
        )
        result = engine.submit_order(market_order)

        assert result.fully_filled
        assert len(result.trades) == 1

    def test_ioc_order(self):
        """Test IOC (Immediate or Cancel) order."""
        engine = MatchingEngine("AAPL")

        # Add sell order
        ask_order = Order(
            order_id="A1",
            symbol="AAPL",
            side=Side.SELL,
            order_type=OrderType.LIMIT,
            price=151.0,
            quantity=50.0,
            timestamp=time.time()
        )
        engine.submit_order(ask_order)

        # Submit IOC buy order for more than available
        ioc_order = Order(
            order_id="I1",
            symbol="AAPL",
            side=Side.BUY,
            order_type=OrderType.IOC,
            price=152.0,
            quantity=100.0,
            timestamp=time.time()
        )
        result = engine.submit_order(ioc_order)

        assert not result.fully_filled
        assert len(result.trades) == 1
        assert result.remaining_order is None  # Remaining cancelled

    def test_fok_order_rejection(self):
        """Test FOK (Fill or Kill) order rejection."""
        engine = MatchingEngine("AAPL")

        # Add sell order
        ask_order = Order(
            order_id="A1",
            symbol="AAPL",
            side=Side.SELL,
            order_type=OrderType.LIMIT,
            price=151.0,
            quantity=50.0,
            timestamp=time.time()
        )
        engine.submit_order(ask_order)

        # Submit FOK buy order for more than available
        fok_order = Order(
            order_id="F1",
            symbol="AAPL",
            side=Side.BUY,
            order_type=OrderType.FOK,
            price=152.0,
            quantity=100.0,
            timestamp=time.time()
        )
        result = engine.submit_order(fok_order)

        assert result.rejected
        assert len(result.trades) == 0


class TestOrderBookReplay:
    """Test order book replay."""

    def test_event_processing(self):
        """Test processing order book events."""
        config = ReplayConfig(
            symbol="AAPL",
            start_time=0.0,
            end_time=100.0,
            speed_multiplier=0.0  # No delay for testing
        )
        replay = OrderBookReplay(config)

        event = OrderBookEvent(
            event_type=EventType.ADD,
            timestamp=1.0,
            symbol="AAPL",
            order_id="O1",
            side=Side.BUY,
            price=150.0,
            quantity=100.0
        )

        result = replay.process_event(event)

        assert result is not None
        assert replay.stats.events_processed == 1
        assert replay.stats.orders_added == 1

    def test_replay_sequence(self):
        """Test replaying a sequence of events."""
        config = ReplayConfig(
            symbol="AAPL",
            start_time=0.0,
            end_time=100.0,
            speed_multiplier=0.0
        )
        replay = OrderBookReplay(config)

        events = [
            OrderBookEvent(
                event_type=EventType.ADD,
                timestamp=1.0,
                symbol="AAPL",
                order_id="A1",
                side=Side.SELL,
                price=151.0,
                quantity=100.0
            ),
            OrderBookEvent(
                event_type=EventType.ADD,
                timestamp=2.0,
                symbol="AAPL",
                order_id="B1",
                side=Side.BUY,
                price=152.0,
                quantity=50.0
            ),
        ]

        stats = replay.replay_events(events)

        assert stats.events_processed == 2
        assert stats.orders_added == 2
        assert len(replay.get_trades()) == 1

    def test_order_book_integrity(self):
        """Test order book integrity validation."""
        config = ReplayConfig(
            symbol="AAPL",
            start_time=0.0,
            end_time=100.0,
            speed_multiplier=0.0
        )
        replay = OrderBookReplay(config)

        events = [
            OrderBookEvent(
                event_type=EventType.ADD,
                timestamp=1.0,
                symbol="AAPL",
                order_id="B1",
                side=Side.BUY,
                price=150.0,
                quantity=100.0
            ),
        ]

        replay.replay_events(events)

        assert replay.validate_integrity()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])