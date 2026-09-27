"""
Performance benchmark comparing Python, C++, and Rust implementations.
"""
from __future__ import annotations

import time
import statistics
from datetime import datetime, timezone
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Python implementation
from simulation.market_simulator import (
    OrderBook as PyOrderBook,
    MatchingEngine as PyMatchingEngine,
    LimitOrder,
    OrderSide,
    OrderType
)

# C++ implementation
try:
    from python.delta.cpp import CPP_AVAILABLE, OrderBook as CppOrderBook, MatchingEngine as CppMatchingEngine, Order, OrderSide as CppOrderSide
except ImportError:
    CPP_AVAILABLE = False
    print("C++ implementation not available. Building required.")

# Rust implementation
try:
    from delta_rust import EventQueue as RustEventQueue, RustBenchmark, EventType
    RUST_AVAILABLE = True
except ImportError:
    RUST_AVAILABLE = False
    print("Rust implementation not available. Building required.")


def benchmark_python_order_book(iterations: int = 100000) -> dict:
    """Benchmark Python order book implementation."""
    print(f"\n=== Benchmarking Python Order Book ({iterations} iterations) ===")
    
    book = PyOrderBook("AAPL", "NYSE")
    engine = PyMatchingEngine("AAPL", "NYSE")
    engine.order_book = book
    
    # Seed order book
    for i in range(10):
        bid_order = LimitOrder(
            order_id=f"BID_{i}",
            side=OrderSide.BUY,
            price=150.0 - i * 0.01,
            quantity=1000,
            timestamp=datetime.now(timezone.utc),
            exchange="NYSE"
        )
        book.add_limit_order(bid_order)
        
        ask_order = LimitOrder(
            order_id=f"ASK_{i}",
            side=OrderSide.SELL,
            price=150.0 + i * 0.01,
            quantity=1000,
            timestamp=datetime.now(timezone.utc),
            exchange="NYSE"
        )
        book.add_limit_order(ask_order)
    
    # Benchmark limit order submissions
    start_time = time.perf_counter()
    
    for i in range(iterations):
        order = LimitOrder(
            order_id=f"ORDER_{i}",
            side=OrderSide.BUY if i % 2 == 0 else OrderSide.SELL,
            price=150.0 + (i % 20) * 0.01,
            quantity=100,
            timestamp=datetime.now(timezone.utc),
            exchange="NYSE"
        )
        engine.submit_limit_order(order, OrderType.GTC)
    
    end_time = time.perf_counter()
    
    elapsed = end_time - start_time
    ops_per_second = iterations / elapsed
    
    return {
        "implementation": "Python",
        "iterations": iterations,
        "elapsed_seconds": elapsed,
        "ops_per_second": ops_per_second
    }


def benchmark_cpp_order_book(iterations: int = 100000) -> dict:
    """Benchmark C++ order book implementation."""
    if not CPP_AVAILABLE:
        return {"implementation": "C++", "status": "not_available"}
    
    print(f"\n=== Benchmarking C++ Order Book ({iterations} iterations) ===")
    
    book = CppOrderBook("AAPL")
    engine = CppMatchingEngine(book)
    
    # Seed order book
    for i in range(10):
        bid_order = Order(
            order_id=i,
            side=CppOrderSide::BUY,
            price=150.0 - i * 0.01,
            quantity=1000.0,
            timestamp_ns=i * 1000,
            participant="DEFAULT"
        )
        book.add_limit_order(bid_order)
        
        ask_order = Order(
            order_id=i + 1000,
            side=CppOrderSide::SELL,
            price=150.0 + i * 0.01,
            quantity=1000.0,
            timestamp_ns=i * 1000,
            participant="DEFAULT"
        )
        book.add_limit_order(ask_order)
    
    # Benchmark limit order submissions
    start_time = time.perf_counter()
    
    for i in range(iterations):
        side = CppOrderSide::BUY if i % 2 == 0 else CppOrderSide::SELL
        order = Order(
            order_id=i + 10000,
            side=side,
            price=150.0 + (i % 20) * 0.01,
            quantity=100.0,
            timestamp_ns=i * 1000,
            participant="DEFAULT"
        )
        engine.submit_limit_order(order, OrderType::LIMIT)
    
    end_time = time.perf_counter()
    
    elapsed = end_time - start_time
    ops_per_second = iterations / elapsed
    
    return {
        "implementation": "C++",
        "iterations": iterations,
        "elapsed_seconds": elapsed,
        "ops_per_second": ops_per_second
    }


def benchmark_rust_event_queue(iterations: int = 100000) -> dict:
    """Benchmark Rust event queue implementation."""
    if not RUST_AVAILABLE:
        return {"implementation": "Rust", "status": "not_available"}
    
    print(f"\n=== Benchmarking Rust Event Queue ({iterations} iterations) ===")
    
    from delta_rust import Event, EventType
    from datetime import datetime
    
    queue = RustEventQueue()
    
    # Benchmark enqueue/dequeue
    start_time = time.perf_counter()
    
    for i in range(iterations):
        event = Event(
            event_id=f"EVENT_{i}",
            event_type=EventType::MARKET_DATA,
            timestamp=datetime.now(timezone.utc),
            symbol="AAPL",
            metadata={}
        )
        queue.enqueue(event)
        queue.dequeue()
    
    end_time = time.perf_counter()
    
    elapsed = end_time - start_time
    ops_per_second = iterations / elapsed
    
    return {
        "implementation": "Rust",
        "iterations": iterations,
        "elapsed_seconds": elapsed,
        "ops_per_second": ops_per_second
    }


def benchmark_rust_native(iterations: int = 100000) -> dict:
    """Benchmark Rust native functions."""
    if not RUST_AVAILABLE:
        return {"implementation": "Rust Native", "status": "not_available"}
    
    print(f"\n=== Benchmarking Rust Native ({iterations} iterations) ===")
    
    benchmark = RustBenchmark()
    ops_per_second = benchmark.benchmark_order_book(iterations)
    
    return {
        "implementation": "Rust Native",
        "iterations": iterations,
        "ops_per_second": ops_per_second
    }


def run_comprehensive_benchmark():
    """Run comprehensive performance comparison."""
    print("=" * 70)
    print("DELTA PERFORMANCE BENCHMARK")
    print("=" * 70)
    
    iterations = 100000
    
    results = []
    
    # Python benchmark
    py_result = benchmark_python_order_book(iterations)
    results.append(py_result)
    
    # C++ benchmark
    cpp_result = benchmark_cpp_order_book(iterations)
    results.append(cpp_result)
    
    # Rust benchmarks
    rust_queue_result = benchmark_rust_event_queue(iterations)
    results.append(rust_queue_result)
    
    rust_native_result = benchmark_rust_native(iterations)
    results.append(rust_native_result)
    
    # Print summary
    print("\n" + "=" * 70)
    print("PERFORMANCE SUMMARY")
    print("=" * 70)
    
    for result in results:
        if result.get("status") == "not_available":
            print(f"{result['implementation']}: NOT AVAILABLE")
        else:
            print(f"{result['implementation']}:")
            print(f"  Iterations: {result['iterations']:,}")
            print(f"  Elapsed: {result['elapsed_seconds']:.4f}s")
            print(f"  Ops/Second: {result['ops_per_second']:,.0f}")
    
    # Calculate speedup
    if all(r.get("status") != "not_available" for r in results[:2]):
        py_ops = results[0]["ops_per_second"]
        cpp_ops = results[1]["ops_per_second"]
        speedup = cpp_ops / py_ops if py_ops > 0 else 0
        
        print("\n" + "=" * 70)
        print(f"C++ SPEEDUP OVER PYTHON: {speedup:.2f}x")
        print("=" * 70)
    
    return results


if __name__ == "__main__":
    results = run_comprehensive_benchmark()
    
    # Save results
    import json
    with open("benchmark_results.json", "w") as f:
        json.dump(results, f, indent=2)
    
    print("\nResults saved to benchmark_results.json")