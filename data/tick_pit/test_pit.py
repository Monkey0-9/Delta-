"""
Test suite for PIT data infrastructure.
"""
from __future__ import annotations

import sys
import os
from datetime import datetime, timezone, timedelta, date
import uuid

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from data.tick_pit import (
    TickData, Quote, Trade, TickType, TickAggregator,
    DataTimestamps, TimestampManager, TimestampType,
    PITStore, PITQuery, PITSnapshot, PITStorageType,
    DataQualityValidator, QualityThresholds, QualityIssue,
    LookaheadBiasDetector, BiasType,
    CorporateAction, CorporateActionHandler, ActionType,
    TradingCalendar, CalendarManager, MarketSession
)


def test_tick_data_structures():
    """Test tick data structures."""
    print("Testing tick data structures...")
    
    # Create quote
    quote = Quote(
        symbol="AAPL",
        exchange="NYSE",
        bid_price=150.0,
        ask_price=150.05,
        bid_size=1000,
        ask_size=1000
    )
    
    print(f"Quote spread: {quote.spread}")
    print(f"Quote mid price: {quote.mid_price}")
    print(f"Quote spread bps: {quote.spread_bps}")
    
    assert abs(quote.spread - 0.05) < 0.001
    assert abs(quote.mid_price - 150.025) < 0.001
    assert quote.spread_bps > 0
    
    # Create trade
    trade = Trade(
        symbol="AAPL",
        exchange="NYSE",
        price=150.0,
        quantity=100
    )
    
    print(f"Trade notional: {trade.notional}")
    
    assert abs(trade.notional - 15000.0) < 0.01
    
    # Create tick data
    tick = TickData.from_quote(quote)
    
    print(f"Tick type: {tick.tick_type}")
    print(f"Tick to dict: {tick.to_dict()}")
    
    assert tick.tick_type == TickType.QUOTE
    
    print("[PASS] Tick data structures test passed")


def test_tick_aggregation():
    """Test tick aggregation."""
    print("\nTesting tick aggregation...")
    
    aggregator = TickAggregator("AAPL")
    
    # Add some ticks
    for i in range(10):
        quote = Quote(
            symbol="AAPL",
            exchange="NYSE",
            bid_price=150.0 + i * 0.01,
            ask_price=150.05 + i * 0.01,
            bid_size=1000,
            ask_size=1000
        )
        tick = TickData.from_quote(quote)
        aggregator.add_tick(tick)
    
    # Aggregate to OHLCV
    start_time = datetime.now(timezone.utc) - timedelta(minutes=10)
    end_time = datetime.now(timezone.utc)
    
    ohlcv = aggregator.aggregate_to_ohlcv(start_time, end_time)
    
    print(f"OHLCV: {ohlcv}")
    
    assert ohlcv["num_ticks"] == 10
    assert ohlcv["open"] is not None
    assert ohlcv["close"] is not None
    
    print("[PASS] Tick aggregation test passed")


def test_timestamp_management():
    """Test timestamp management."""
    print("\nTesting timestamp management...")
    
    # Create timestamps
    timestamps = DataTimestamps(
        event_time=datetime.now(timezone.utc) - timedelta(seconds=10),
        source_timestamp=datetime.now(timezone.utc) - timedelta(seconds=5),
        publication_timestamp=datetime.now(timezone.utc) - timedelta(seconds=3),
        available_timestamp=datetime.now(timezone.utc) - timedelta(seconds=1)
    )
    
    print(f"Timestamp validation: {timestamps.validate_consistency()}")
    
    # Should be valid (no errors)
    assert len(timestamps.validate_consistency()) == 0
    
    # Test timestamp manager
    manager = TimestampManager()
    
    event_time = datetime.now(timezone.utc) - timedelta(seconds=10)
    created_timestamps = manager.create_timestamps(event_time, "DEFAULT")
    
    print(f"Created timestamps: {created_timestamps.to_dict()}")
    
    assert created_timestamps.available_timestamp >= created_timestamps.event_time
    
    print("[PASS] Timestamp management test passed")


def test_pit_store():
    """Test PIT store."""
    print("\nTesting PIT store...")
    
    # Create file-based PIT store for testing
    import tempfile
    import os
    fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    
    try:
        pit_store = PITStore(db_path=db_path)
    
        # Create some test data
        quote = Quote(
            symbol="AAPL",
            exchange="NYSE",
            bid_price=150.0,
            ask_price=150.05,
            bid_size=1000,
            ask_size=1000
        )
        
        tick = TickData.from_quote(quote)
        
        timestamps = DataTimestamps(
            event_time=datetime.now(timezone.utc) - timedelta(seconds=10),
            source_timestamp=datetime.now(timezone.utc) - timedelta(seconds=5),
            publication_timestamp=datetime.now(timezone.utc) - timedelta(seconds=3),
            available_timestamp=datetime.now(timezone.utc) - timedelta(seconds=1)
        )
        
        # Store tick
        tick_id = pit_store.store_tick(tick, timestamps, "NYSE", 1.0)
        
        print(f"Stored tick ID: {tick_id}")
        
        # Query as of
        query = PITQuery(
            symbol="AAPL",
            as_of=datetime.now(timezone.utc)
        )
        
        snapshot = pit_store.query_as_of(query)
        
        print(f"Snapshot ticks: {len(snapshot.ticks)}")
        print(f"Snapshot hash: {snapshot.snapshot_hash}")
        
        assert len(snapshot.ticks) > 0
        assert snapshot.snapshot_hash is not None
        
        pit_store.close()
        
        print("[PASS] PIT store test passed")
        
    finally:
        # Clean up
        if os.path.exists(db_path):
            os.remove(db_path)


def test_data_quality_validation():
    """Test data quality validation."""
    print("\nTesting data quality validation...")
    
    validator = DataQualityValidator()
    
    # Create valid quote
    valid_quote = Quote(
        symbol="AAPL",
        exchange="NYSE",
        bid_price=150.0,
        ask_price=150.05,
        bid_size=1000,
        ask_size=1000
    )
    
    tick = TickData.from_quote(valid_quote)
    result = validator.validate_tick(tick)
    
    print(f"Valid tick result: {result.to_dict()}")
    
    assert result.is_valid
    assert result.quality_score > 0.9
    
    # Create invalid quote (crossed market)
    invalid_quote = Quote(
        symbol="AAPL",
        exchange="NYSE",
        bid_price=151.0,  # Higher than ask
        ask_price=150.0,
        bid_size=1000,
        ask_size=1000
    )
    
    invalid_tick = TickData.from_quote(invalid_quote)
    invalid_result = validator.validate_tick(invalid_tick)
    
    print(f"Invalid tick result: {invalid_result.to_dict()}")
    
    assert not invalid_result.is_valid
    assert len(invalid_result.issues) > 0
    
    print("[PASS] Data quality validation test passed")


def test_lookahead_bias_detection():
    """Test lookahead bias detection."""
    print("\nTesting lookahead bias detection...")
    
    detector = LookaheadBiasDetector()
    
    # Create valid tick
    quote = Quote(
        symbol="AAPL",
        exchange="NYSE",
        bid_price=150.0,
        ask_price=150.05,
        bid_size=1000,
        ask_size=1000
    )
    
    tick = TickData.from_quote(quote)
    
    timestamps = DataTimestamps(
        event_time=datetime.now(timezone.utc) - timedelta(seconds=10),
        source_timestamp=datetime.now(timezone.utc) - timedelta(seconds=5),
        publication_timestamp=datetime.now(timezone.utc) - timedelta(seconds=3),
        available_timestamp=datetime.now(timezone.utc) - timedelta(seconds=1)
    )
    
    # Valid case (no bias)
    result = detector.validate_temporal_boundary(tick, timestamps)
    
    print(f"Valid bias check: {result.to_dict()}")
    
    assert not result.has_bias
    
    # Invalid case (data available after decision)
    future_timestamps = DataTimestamps(
        event_time=datetime.now(timezone.utc) - timedelta(seconds=10),
        source_timestamp=datetime.now(timezone.utc) - timedelta(seconds=5),
        publication_timestamp=datetime.now(timezone.utc) - timedelta(seconds=3),
        available_timestamp=datetime.now(timezone.utc) + timedelta(seconds=10)  # Future
    )
    
    decision_time = datetime.now(timezone.utc)
    invalid_result = detector.validate_temporal_boundary(tick, future_timestamps, decision_time)
    
    print(f"Invalid bias check: {invalid_result.to_dict()}")
    
    assert invalid_result.has_bias
    
    print("[PASS] Lookahead bias detection test passed")


def test_corporate_actions():
    """Test corporate action handling."""
    print("\nTesting corporate actions...")
    
    handler = CorporateActionHandler()
    
    # Add stock split
    split_action = CorporateAction(
        action_id="SPLIT_001",
        symbol="AAPL",
        action_type=ActionType.STOCK_SPLIT,
        announcement_date=date(2024, 1, 15),
        ex_date=date(2024, 2, 1),
        record_date=date(2024, 2, 5),
        split_ratio=2.0,  # 2-for-1 split
        description="2-for-1 stock split"
    )
    
    handler.add_action(split_action)
    
    # Test price adjustment
    original_price = 200.0
    as_of = datetime(2024, 2, 2, tzinfo=timezone.utc)
    
    adjusted_price, applied_action = handler.adjust_price_for_split(original_price, "AAPL", as_of)
    
    print(f"Original price: {original_price}")
    print(f"Adjusted price: {adjusted_price}")
    print(f"Applied action: {applied_action.to_dict() if applied_action else None}")
    
    assert abs(adjusted_price - 100.0) < 0.01  # 200 / 2 = 100
    assert applied_action is not None
    
    print("[PASS] Corporate actions test passed")


def test_trading_calendar():
    """Test trading calendar."""
    print("\nTesting trading calendar...")
    
    calendar = TradingCalendar("NYSE")
    
    # Test trading day check
    trading_date = date(2024, 1, 16)  # Tuesday
    weekend_date = date(2024, 1, 13)  # Saturday
    
    is_trading = calendar.is_trading_day(trading_date)
    is_weekend = calendar.is_trading_day(weekend_date)
    
    print(f"Is trading day (weekday): {is_trading}")
    print(f"Is trading day (weekend): {is_weekend}")
    
    assert is_trading
    assert not is_weekend
    
    # Test market session
    trading_datetime = datetime(2024, 1, 16, 10, 0, tzinfo=timezone.utc)
    after_hours = datetime(2024, 1, 16, 20, 0, tzinfo=timezone.utc)
    
    session = calendar.get_market_session(trading_datetime)
    evening_session = calendar.get_market_session(after_hours)
    
    print(f"Day session: {session}")
    print(f"Evening session: {evening_session}")
    
    assert session == MarketSession.REGULAR
    assert evening_session == MarketSession.AFTER_HOURS
    
    print("[PASS] Trading calendar test passed")


def test_calendar_manager():
    """Test calendar manager."""
    print("\nTesting calendar manager...")
    
    manager = CalendarManager()
    
    # Get NYSE calendar
    nyse_calendar = manager.get_calendar("NYSE")
    
    print(f"NYSE calendar: {nyse_calendar.exchange}")
    
    assert nyse_calendar is not None
    
    # Test common trading days
    start_date = date(2024, 1, 15)
    end_date = date(2024, 1, 19)
    
    common_days = manager.get_common_trading_days(start_date, end_date, ["NYSE", "NASDAQ"])
    
    print(f"Common trading days: {len(common_days)}")
    
    assert len(common_days) > 0
    
    print("[PASS] Calendar manager test passed")


def run_all_tests():
    """Run all tests."""
    print("=" * 60)
    print("PIT DATA INFRASTRUCTURE TEST SUITE")
    print("=" * 60)
    
    try:
        test_tick_data_structures()
        test_tick_aggregation()
        test_timestamp_management()
        test_pit_store()
        test_data_quality_validation()
        test_lookahead_bias_detection()
        test_corporate_actions()
        test_trading_calendar()
        test_calendar_manager()
        
        print("\n" + "=" * 60)
        print("ALL TESTS PASSED [SUCCESS]")
        print("=" * 60)
        
    except AssertionError as e:
        print(f"\n[FAIL] TEST FAILED: {e}")
        return False
    except Exception as e:
        print(f"\n[ERROR] ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)