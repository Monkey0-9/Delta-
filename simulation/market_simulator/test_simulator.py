"""
Test suite for the integrated market simulator.
"""
from __future__ import annotations

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from simulation.market_simulator import (
    IntegratedMarketSimulator,
    OrderSide,
    OrderType,
    LatencyDistribution
)


def test_basic_order_book():
    """Test basic order book functionality."""
    print("Testing basic order book...")
    
    simulator = IntegratedMarketSimulator("AAPL", "NYSE")
    simulator.seed_order_book(num_bids=5, num_asks=5, base_price=150.0)
    
    # Check order book state
    market_state = simulator.get_market_state()
    print(f"Best bid: {market_state['order_book']['bids'][0]}")
    print(f"Best ask: {market_state['order_book']['asks'][0]}")
    print(f"Spread: {market_state['order_book']['spread']}")
    
    assert len(market_state['order_book']['bids']) == 5
    assert len(market_state['order_book']['asks']) == 5
    assert market_state['order_book']['spread'] > 0
    
    print("[PASS] Basic order book test passed")


def test_limit_order_execution():
    """Test limit order execution."""
    print("\nTesting limit order execution...")
    
    simulator = IntegratedMarketSimulator("AAPL", "NYSE")
    simulator.seed_order_book(num_bids=5, num_asks=5, base_price=150.0)
    
    # Submit aggressive buy order (should fill immediately)
    # Get current best ask and set price above it
    market_state = simulator.get_market_state()
    best_ask = market_state['order_book']['asks'][0]['price']
    result = simulator.submit_limit_order(
        side="BUY",
        price=best_ask + 0.01,  # Above best ask
        quantity=100,
        order_type=OrderType.GTC
    )
    
    print(f"Order ID: {result.order_id}")
    print(f"Status: {result.execution_result.status}")
    print(f"Filled quantity: {result.execution_result.filled_quantity}")
    print(f"Average price: {result.execution_result.average_price}")
    print(f"Latency: {result.latency_ms} ms")
    
    assert result.execution_result.filled_quantity > 0
    assert result.execution_result.status.value in ["FILLED", "PARTIALLY_FILLED"]
    assert result.latency_ms > 0
    
    print("[PASS] Limit order execution test passed")


def test_market_order_execution():
    """Test market order execution."""
    print("\nTesting market order execution...")
    
    simulator = IntegratedMarketSimulator("AAPL", "NYSE")
    simulator.seed_order_book(num_bids=5, num_asks=5, base_price=150.0)
    
    # Submit market buy order
    result = simulator.submit_market_order(
        side="BUY",
        quantity=200
    )
    
    print(f"Order ID: {result.order_id}")
    print(f"Status: {result.execution_result.status}")
    print(f"Filled quantity: {result.execution_result.filled_quantity}")
    print(f"Average price: {result.execution_result.average_price}")
    print(f"Market impact: {result.market_impact}")
    print(f"Fees: {result.fee_calculation}")
    
    assert result.execution_result.filled_quantity > 0
    assert result.market_impact is not None
    assert result.fee_calculation is not None
    
    print("[PASS] Market order execution test passed")


def test_queue_position_analysis():
    """Test queue position analysis."""
    print("\nTesting queue position analysis...")
    
    simulator = IntegratedMarketSimulator("AAPL", "NYSE")
    simulator.seed_order_book(num_bids=5, num_asks=5, base_price=150.0)
    
    # Submit passive buy order (should rest in book)
    result = simulator.submit_limit_order(
        side="BUY",
        price=149.0,  # Below best bid
        quantity=100,
        order_type=OrderType.GTC
    )
    
    print(f"Queue position info: {result.queue_position_info}")
    
    if result.queue_position_info:
        print(f"Queue position: {result.queue_position_info.queue_position}")
        print(f"Queue length: {result.queue_position_info.queue_length}")
        print(f"Fill probability: {result.queue_position_info.fill_probability}")
        print(f"Adverse selection risk: {result.queue_position_info.adverse_selection_risk}")
        
        assert result.queue_position_info.queue_position >= 0
        assert 0 <= result.queue_position_info.fill_probability <= 1
    
    print("[PASS] Queue position analysis test passed")


def test_latency_modeling():
    """Test latency modeling."""
    print("\nTesting latency modeling...")
    
    simulator = IntegratedMarketSimulator("AAPL", "NYSE", 
                                         latency_distribution=LatencyDistribution.LOG_NORMAL)
    simulator.seed_order_book(num_bids=5, num_asks=5, base_price=150.0)
    
    # Submit multiple orders to build latency history
    for i in range(10):
        simulator.submit_limit_order(
            side="BUY",
            price=151.0,
            quantity=100,
            order_type=OrderType.GTC
        )
    
    # Get latency statistics
    latency_stats = simulator.latency_model.get_percentiles()
    print(f"Latency percentiles: {latency_stats}")
    
    # Check SLA compliance
    sla_compliance = simulator.latency_model.check_sla_compliance()
    print(f"SLA compliance: {sla_compliance}")
    
    assert latency_stats["p50"] > 0
    assert latency_stats["p95"] > 0
    assert latency_stats["p99"] > 0
    
    print("[PASS] Latency modeling test passed")


def test_market_impact():
    """Test market impact calculation."""
    print("\nTesting market impact calculation...")
    
    simulator = IntegratedMarketSimulator("AAPL", "NYSE")
    simulator.seed_order_book(num_bids=5, num_asks=5, base_price=150.0)
    
    # Submit large order to see impact
    result = simulator.submit_market_order(
        side="BUY",
        quantity=5000  # Large order
    )
    
    print(f"Market impact: {result.market_impact}")
    
    if result.market_impact:
        assert result.market_impact["total_impact_bps"] > 0
        assert result.market_impact["permanent_impact_bps"] >= 0
        assert result.market_impact["temporary_impact_bps"] >= 0
    
    print("[PASS] Market impact test passed")


def test_fee_calculation():
    """Test fee calculation."""
    print("\nTesting fee calculation...")
    
    simulator = IntegratedMarketSimulator("AAPL", "NYSE")
    simulator.seed_order_book(num_bids=5, num_asks=5, base_price=150.0)
    
    # Submit order
    result = simulator.submit_limit_order(
        side="BUY",
        price=151.0,
        quantity=1000,
        order_type=OrderType.GTC
    )
    
    print(f"Fee calculation: {result.fee_calculation}")
    
    if result.fee_calculation:
        assert "fee_usd" in result.fee_calculation
        assert "rebate_usd" in result.fee_calculation
        assert "net_cost_usd" in result.fee_calculation
    
    print("[PASS] Fee calculation test passed")


def test_adverse_selection():
    """Test adverse selection modeling."""
    print("\nTesting adverse selection modeling...")
    
    simulator = IntegratedMarketSimulator("AAPL", "NYSE")
    simulator.seed_order_book(num_bids=5, num_asks=5, base_price=150.0)
    
    # Submit passive order to get queue position
    result = simulator.submit_limit_order(
        side="BUY",
        price=149.0,
        quantity=100,
        order_type=OrderType.GTC
    )
    
    print(f"Adverse selection: {result.adverse_selection}")
    
    if result.adverse_selection:
        assert "total_adverse_selection_bps" in result.adverse_selection
        assert "toxicity_score" in result.adverse_selection
        assert 0 <= result.adverse_selection["toxicity_score"] <= 1
    
    print("[PASS] Adverse selection test passed")


def test_complete_simulation():
    """Test complete simulation with all components."""
    print("\nTesting complete simulation...")
    
    simulator = IntegratedMarketSimulator("AAPL", "NYSE")
    simulator.seed_order_book(num_bids=10, num_asks=10, base_price=150.0)
    
    # Run multiple simulations
    for i in range(5):
        simulator.submit_limit_order(
            side="BUY" if i % 2 == 0 else "SELL",
            price=150.0 + (i * 0.5),
            quantity=100 * (i + 1),
            order_type=OrderType.GTC
        )
    
    # Get simulation summary
    summary = simulator.get_simulation_summary()
    print(f"Simulation summary: {summary}")
    
    assert summary["total_simulations"] == 5
    assert summary["avg_latency_ms"] > 0
    assert 0 <= summary["fill_rate"] <= 1
    
    print("[PASS] Complete simulation test passed")


def run_all_tests():
    """Run all tests."""
    print("=" * 60)
    print("INSTITUTIONAL MARKET SIMULATOR TEST SUITE")
    print("=" * 60)
    
    try:
        test_basic_order_book()
        test_limit_order_execution()
        test_market_order_execution()
        test_queue_position_analysis()
        test_latency_modeling()
        test_market_impact()
        test_fee_calculation()
        test_adverse_selection()
        test_complete_simulation()
        
        print("\n" + "=" * 60)
        print("ALL TESTS PASSED [PASS]")
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