"""
Tests for Python-Rust bridge.
"""

import pytest

from native.rust_bridge import (
    RustBridge,
    get_rust_bridge,
    rust_available,
)


class TestRustBridge:
    """Test Rust bridge functionality."""
    
    def test_bridge_creation(self):
        """Test bridge instance creation."""
        bridge = RustBridge()
        assert bridge is not None
        assert isinstance(bridge.is_available(), bool)
    
    def test_global_bridge(self):
        """Test global bridge singleton."""
        bridge1 = get_rust_bridge()
        bridge2 = get_rust_bridge()
        assert bridge1 is bridge2
    
    def test_rust_available_check(self):
        """Test Rust availability check."""
        available = rust_available()
        assert isinstance(available, bool)
    
    def test_checksum_u64_python_fallback(self):
        """Test checksum with Python fallback."""
        bridge = RustBridge()
        values = [1, 2, 3, 4, 5]
        result = bridge.checksum_u64(values)
        assert result == 15
    
    def test_normalize_dedup_python_fallback(self):
        """Test normalize dedup with Python fallback."""
        bridge = RustBridge()
        values = [1, 1, 2, 3, 3, 3, 4]
        result = bridge.normalize_dedup(values)
        assert result == [1, 2, 3, 4]
    
    def test_feature_returns_python_fallback(self):
        """Test feature returns with Python fallback."""
        bridge = RustBridge()
        prices = [100.0, 110.0, 110.0, 55.0]
        result = bridge.feature_returns(prices)
        assert len(result) == 3
        assert abs(result[0] - 0.1) < 1e-9
        assert abs(result[1] - 0.0) < 1e-9
        assert abs(result[2] + 0.5) < 1e-9
    
    def test_replay_inversions_python_fallback(self):
        """Test replay inversions with Python fallback."""
        bridge = RustBridge()
        timestamps = [1, 2, 3]
        result = bridge.replay_inversions(timestamps)
        assert result == 0
        
        timestamps = [3, 2, 1]
        result = bridge.replay_inversions(timestamps)
        assert result == 3
    
    def test_risk_gross_exposure_python_fallback(self):
        """Test risk gross exposure with Python fallback."""
        bridge = RustBridge()
        quantities = [10, 5]
        prices = [100, 200]
        result = bridge.risk_gross_exposure(quantities, prices)
        assert result == 2000
    
    def test_match_orders_python_fallback(self):
        """Test match orders with Python fallback."""
        bridge = RustBridge()
        result = bridge.match_orders(10, [4, 4, 4])
        assert result == (10, 0)
        
        result = bridge.match_orders(20, [4, 4])
        assert result == (8, 12)
    
    def test_normalize_market_events_python_fallback(self):
        """Test normalize market events with Python fallback."""
        bridge = RustBridge()
        events = [(2.0, 100.0), (1.0, 95.0), (2.0, 100.0)]
        result = bridge.normalize_market_events(events)
        assert len(result) == 2
        assert result[0] == (1.0, 95.0)
        assert result[1] == (2.0, 100.0)
    
    def test_serialize_event_json_python_fallback(self):
        """Test serialize event JSON with Python fallback."""
        bridge = RustBridge()
        event_data = [("symbol", "AAPL"), ("price", "150.25")]
        result = bridge.serialize_event_json(event_data)
        assert "symbol" in result
        assert "AAPL" in result
        assert "price" in result
        assert "150.25" in result
    
    def test_empty_inputs(self):
        """Test handling of empty inputs."""
        bridge = RustBridge()
        
        assert bridge.checksum_u64([]) == 0
        assert bridge.normalize_dedup([]) == []
        assert bridge.feature_returns([]) == []
        assert bridge.replay_inversions([]) == 0
        assert bridge.normalize_market_events([]) == []