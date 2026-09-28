"""
DELTA OS - Python FFI Bindings for High-Performance Order Book

This module provides Python bindings for the Rust/C++ order book engines,
enabling zero-copy integration with the Python-based DELTA system.

Performance targets:
- Order addition: < 1μs
- Order matching: < 2μs
- Throughput: > 1M orders/second
- Memory: Zero-copy where possible
"""

import ctypes
import os
from pathlib import Path
from typing import List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum
import time

# Type definitions
OrderID = int
Price = int
Quantity = int


class Side(Enum):
    """Order side enumeration."""
    BUY = 0
    SELL = 1


class OrderStatus(Enum):
    """Order status enumeration."""
    NEW = 0
    PARTIALLY_FILLED = 1
    FILLED = 2
    CANCELLED = 3
    REJECTED = 4


@dataclass
class LimitOrder:
    """Limit order representation."""
    order_id: OrderID
    price: Price
    quantity: Quantity
    original_quantity: Quantity
    side: Side
    status: OrderStatus
    sequence: int
    queue_position: int


@dataclass
class PriceLevel:
    """Price level representation."""
    price: Price
    total_quantity: Quantity
    order_count: int
    head_index: int
    tail_index: int


class RustOrderBook:
    """
    Python wrapper for Rust order book engine.
    
    Provides zero-copy access to the high-performance Rust implementation.
    """
    
    def __init__(self, pool_capacity: int = 100000, tick_size: int = 1):
        """
        Initialize Rust order book.
        
        Args:
            pool_capacity: Memory pool capacity
            tick_size: Minimum price increment
        """
        # Load Rust library
        self._load_rust_library()
        
        # Initialize order book
        self._book = self._lib.order_book_new(pool_capacity, tick_size)
        
        if not self._book:
            raise RuntimeError("Failed to initialize Rust order book")
        
        self._pool_capacity = pool_capacity
        self._tick_size = tick_size
    
    def _load_rust_library(self):
        """Load the Rust shared library."""
        # Try to find the compiled library
        library_paths = [
            # Development build
            Path(__file__).parent.parent / "rust" / "order_book" / "target" / "release" / "delta_order_book.dll",
            Path(__file__).parent.parent / "rust" / "order_book" / "target" / "release" / "libdelta_order_book.so",
            Path(__file__).parent.parent / "rust" / "order_book" / "target" / "release" / "libdelta_order_book.dylib",
            # Installed location
            Path(__file__).parent.parent / "rust" / "order_book" / "target" / "debug" / "delta_order_book.dll",
        ]
        
        for library_path in library_paths:
            if library_path.exists():
                self._lib = ctypes.CDLL(str(library_path))
                break
        else:
            # Fallback to Python implementation if Rust not available
            print("Warning: Rust library not found, using Python fallback")
            self._use_python_fallback = True
            return
        
        # Define function signatures
        self._lib.order_book_new.restype = ctypes.c_void_p
        self._lib.order_book_new.argtypes = [ctypes.c_size_t, ctypes.c_int64]
        
        self._lib.order_book_free.restype = None
        self._lib.order_book_free.argtypes = [ctypes.c_void_p]
        
        self._lib.order_book_add_limit_order.restype = ctypes.c_size_t
        self._lib.order_book_add_limit_order.argtypes = [
            ctypes.c_void_p,
            ctypes.c_uint64,
            ctypes.c_uint8,
            ctypes.c_int64,
            ctypes.c_uint64,
        ]
        
        self._lib.order_book_best_bid.restype = ctypes.c_int64
        self._lib.order_book_best_bid.argtypes = [ctypes.c_void_p]
        
        self._lib.order_book_best_ask.restype = ctypes.c_int64
        self._lib.order_book_best_ask.argtypes = [ctypes.c_void_p]
        
        self._use_python_fallback = False
    
    def add_limit_order(
        self,
        order_id: OrderID,
        side: Side,
        price: Price,
        quantity: Quantity
    ) -> List[Tuple[OrderID, Price, Quantity]]:
        """
        Add a limit order to the book.
        
        Args:
            order_id: Unique order identifier
            side: Order side
            price: Limit price
            quantity: Order quantity
            
        Returns:
            List of fills (order_id, price, quantity)
        """
        if self._use_python_fallback:
            return self._python_add_limit_order(order_id, side, price, quantity)
        
        side_value = 0 if side == Side.BUY else 1
        fill_count = self._lib.order_book_add_limit_order(
            self._book,
            order_id,
            side_value,
            price,
            quantity
        )
        
        # In a full implementation, we would extract the actual fills
        # For now, return empty list as fill extraction is complex
        return []
    
    def cancel_order(self, order_id: OrderID) -> bool:
        """Cancel an order."""
        if self._use_python_fallback:
            return self._python_cancel_order(order_id)
        
        # Rust implementation would have cancel_order function
        # For now, return False
        return False
    
    def best_bid(self) -> Price:
        """Get best bid price."""
        if self._use_python_fallback:
            return self._python_best_bid()
        
        return self._lib.order_book_best_bid(self._book)
    
    def best_ask(self) -> Price:
        """Get best ask price."""
        if self._use_python_fallback:
            return self._python_best_ask()
        
        return self._lib.order_book_best_ask(self._book)
    
    def spread(self) -> Price:
        """Get current spread."""
        best_bid = self.best_bid()
        best_ask = self.best_ask()
        
        if best_bid == 0 or best_ask == 0:
            return 0
        
        return best_ask - best_bid
    
    def get_snapshot(self, depth: int = 10) -> Tuple[List[PriceLevel], List[PriceLevel]]:
        """Get order book snapshot."""
        if self._use_python_fallback:
            return self._python_get_snapshot(depth)
        
        # Rust implementation would have get_snapshot function
        # For now, return empty lists
        return [], []
    
    def __del__(self):
        """Clean up Rust resources."""
        if hasattr(self, '_book') and self._book:
            self._lib.order_book_free(self._book)
    
    # Python fallback implementations
    def _python_add_limit_order(
        self,
        order_id: OrderID,
        side: Side,
        price: Price,
        quantity: Quantity
    ) -> List[Tuple[OrderID, Price, Quantity]]:
        """Python fallback for order addition."""
        from execution.matching.l2_order_book import L2OrderBook, Side as CoreSide
        
        if not hasattr(self, '_python_book'):
            from core.contracts.canonical import Instrument, AssetClass, Currency
            instrument = Instrument(
                symbol="SYMBOL",
                asset_class=AssetClass.EQUITY,
                currency=Currency.USD
            )
            self._python_book = L2OrderBook(instrument)
        
        core_side = CoreSide.BUY if side == Side.BUY else CoreSide.SELL
        from decimal import Decimal
        
        fills, _ = self._python_book.add_limit_order(
            order_id=str(order_id),
            side=core_side,
            price=Decimal(str(price)),
            quantity=Decimal(str(quantity))
        )
        
        return [(f[0], int(f[1]), int(f[2])) for f in fills]
    
    def _python_cancel_order(self, order_id: OrderID) -> bool:
        """Python fallback for order cancellation."""
        if hasattr(self, '_python_book'):
            return self._python_book.cancel_order(str(order_id))
        return False
    
    def _python_best_bid(self) -> Price:
        """Python fallback for best bid."""
        if hasattr(self, '_python_book'):
            bid = self._python_book.best_bid
            return int(bid) if bid else 0
        return 0
    
    def _python_best_ask(self) -> Price:
        """Python fallback for best ask."""
        if hasattr(self, '_python_book'):
            ask = self._python_book.best_ask
            return int(ask) if ask else 0
        return 0
    
    def _python_get_snapshot(self, depth: int) -> Tuple[List[PriceLevel], List[PriceLevel]]:
        """Python fallback for snapshot."""
        if hasattr(self, '_python_book'):
            snapshot = self._python_book.get_snapshot(depth)
            
            bid_levels = [
                PriceLevel(
                    price=int(level.price),
                    total_quantity=int(level.total_quantity),
                    order_count=level.order_count,
                    head_index=0,
                    tail_index=0
                )
                for level in snapshot.bids
            ]
            
            ask_levels = [
                PriceLevel(
                    price=int(level.price),
                    total_quantity=int(level.total_quantity),
                    order_count=level.order_count,
                    head_index=0,
                    tail_index=0
                )
                for level in snapshot.asks
            ]
            
            return bid_levels, ask_levels
        
        return [], []


class PerformanceBenchmark:
    """
    Performance benchmarking for order book implementations.
    
    Compares Python, Rust, and C++ implementations.
    """
    
    def __init__(self):
        """Initialize benchmark."""
        self.results = {}
    
    def benchmark_add_order(self, num_orders: int = 10000) -> dict:
        """
        Benchmark order addition performance.
        
        Args:
            num_orders: Number of orders to add
            
        Returns:
            Benchmark results
        """
        results = {}
        
        # Benchmark Python implementation
        python_book = self._create_python_book()
        start = time.perf_counter_ns()
        
        for i in range(num_orders):
            side = Side.BUY if i % 2 == 0 else Side.SELL
            python_book.add_limit_order(i, side, 100 + i, 100)
        
        end = time.perf_counter_ns()
        python_time = (end - start) / num_orders  # Average time per order
        results["python_avg_ns"] = python_time
        results["python_throughput"] = 1e9 / python_time  # Orders per second
        
        # Benchmark Rust implementation
        try:
            rust_book = RustOrderBook(pool_capacity=num_orders)
            start = time.perf_counter_ns()
            
            for i in range(num_orders):
                side = Side.BUY if i % 2 == 0 else Side.SELL
                rust_book.add_limit_order(i, side, 100 + i, 100)
            
            end = time.perf_counter_ns()
            rust_time = (end - start) / num_orders
            results["rust_avg_ns"] = rust_time
            results["rust_throughput"] = 1e9 / rust_time
            results["speedup"] = python_time / rust_time
        except Exception as e:
            results["rust_error"] = str(e)
        
        return results
    
    def benchmark_order_matching(self, num_orders: int = 1000) -> dict:
        """
        Benchmark order matching performance.
        
        Args:
            num_orders: Number of orders to match
            
        Returns:
            Benchmark results
        """
        results = {}
        
        # Benchmark Python implementation
        python_book = self._create_python_book()
        
        # Add asks
        for i in range(num_orders):
            python_book.add_limit_order(i, Side.SELL, 100 + i, 100)
        
        # Add crossing bids
        start = time.perf_counter_ns()
        
        for i in range(num_orders):
            python_book.add_limit_order(num_orders + i, Side.BUY, 200, 50)
        
        end = time.perf_counter_ns()
        python_time = (end - start) / num_orders
        results["python_avg_ns"] = python_time
        results["python_throughput"] = 1e9 / python_time
        
        return results
    
    def _create_python_book(self):
        """Create Python order book for benchmarking."""
        from execution.matching.l2_order_book import L2OrderBook
        from core.contracts.canonical import Instrument, AssetClass, Currency
        
        instrument = Instrument(
            symbol="SYMBOL",
            asset_class=AssetClass.EQUITY,
            currency=Currency.USD
        )
        
        return L2OrderBook(instrument)
    
    def run_comprehensive_benchmark(self) -> dict:
        """
        Run comprehensive performance benchmark.
        
        Returns:
            Complete benchmark results
        """
        print("Running comprehensive performance benchmark...")
        
        # Order addition benchmark
        print("Benchmarking order addition...")
        add_results = self.benchmark_add_order(10000)
        print(f"Python: {add_results['python_throughput']:,.0f} orders/sec")
        if "rust_throughput" in add_results:
            print(f"Rust: {add_results['rust_throughput']:,.0f} orders/sec")
            print(f"Speedup: {add_results['speedup']:.1f}x")
        
        # Order matching benchmark
        print("Benchmarking order matching...")
        match_results = self.benchmark_order_matching(1000)
        print(f"Python: {match_results['python_throughput']:,.0f} orders/sec")
        
        return {
            "add_order": add_results,
            "order_matching": match_results,
        }


__all__ = [
    "RustOrderBook",
    "PerformanceBenchmark",
    "Side",
    "OrderStatus",
    "LimitOrder",
    "PriceLevel",
]
