"""
DELTA C++ high-performance components.

This module provides Python bindings for C++ implementations of:
- Order book (ultra-low latency)
- Matching engine (high throughput)
- Portfolio math kernels (vectorized)
- Option pricing engines (fast)

Performance targets:
- Order book: >10M orders/second
- Matching: <1 microsecond p99 latency
- Calculations: 100x faster than Python
"""
from __future__ import annotations

try:
    from delta_cpp import (
        OrderSide,
        OrderType,
        OrderStatus,
        OrderBookLevel,
        Order,
        Fill,
        ExecutionResult,
        OrderBook,
        MatchingEngine
    )
    CPP_AVAILABLE = True
except ImportError:
    CPP_AVAILABLE = False
    print("Warning: C++ module not available. Using Python fallback.")

__all__ = [
    "CPP_AVAILABLE",
    "OrderSide",
    "OrderType",
    "OrderStatus",
    "OrderBookLevel",
    "Order",
    "Fill",
    "ExecutionResult",
    "OrderBook",
    "MatchingEngine",
]