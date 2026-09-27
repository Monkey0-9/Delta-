"""
Python-Rust bridge for DELTA native kernels.

Provides Python access to high-performance Rust implementations
via PyO3 bindings. This module serves as the interface layer for
the three-language architecture.

When maturin is installed and the Rust library is built with the
python feature, this module will import the compiled Rust extension.
Otherwise, it provides Python fallback implementations.
"""

import os
import sys
from typing import Optional

# Try to import the compiled Rust extension
try:
    # Import the compiled Rust module
    import delta_native
    RUST_AVAILABLE = True
except ImportError:
    RUST_AVAILABLE = False
    delta_native = None


class RustBridge:
    """
    Bridge to Rust native kernels.
    
    Provides access to high-performance Rust implementations
    for quantitative computing operations.
    """
    
    def __init__(self):
        self.rust_available = RUST_AVAILABLE
        self._native = delta_native if RUST_AVAILABLE else None
    
    def is_available(self) -> bool:
        """Check if Rust native implementation is available."""
        return self.rust_available
    
    def checksum_u64(self, values: list[int]) -> int:
        """
        Compute checksum of u64 values.
        
        Args:
            values: List of u64 integers
            
        Returns:
            Checksum value
        """
        if self._native:
            return self._native.checksum_u64_py(values)
        # Python fallback
        return sum(values)
    
    def normalize_dedup(self, values: list[int]) -> list[int]:
        """
        Normalize and deduplicate values.
        
        Args:
            values: List of i64 integers
            
        Returns:
            Deduplicated and normalized list
        """
        if self._native:
            return self._native.normalize_dedup_py(values)
        # Python fallback
        seen = set()
        result = []
        for v in values:
            if v not in seen:
                seen.add(v)
                result.append(v)
        return result
    
    def feature_returns(self, prices: list[float]) -> list[float]:
        """
        Compute feature returns from prices.
        
        Args:
            prices: List of price values
            
        Returns:
            List of returns
        """
        if self._native:
            return self._native.feature_returns_py(prices)
        # Python fallback
        if len(prices) < 2:
            return []
        returns = []
        for i in range(len(prices) - 1):
            base = abs(prices[i])
            if base == 0:
                returns.append(0.0)
            else:
                returns.append((prices[i + 1] - prices[i]) / base)
        return returns
    
    def replay_inversions(self, timestamps: list[int]) -> int:
        """
        Count out-of-order timestamp inversions.
        
        Args:
            timestamps: List of timestamp values
            
        Returns:
            Number of inversions
        """
        if self._native:
            return self._native.replay_inversions_py(timestamps)
        # Python fallback
        inv = 0
        for i in range(len(timestamps)):
            for j in range(i + 1, len(timestamps)):
                if timestamps[i] > timestamps[j]:
                    inv += 1
        return inv
    
    def risk_gross_exposure(self, quantities: list[int], prices: list[int]) -> int:
        """
        Compute gross exposure for risk management.
        
        Args:
            quantities: List of quantities
            prices: List of prices
            
        Returns:
            Gross exposure value
        """
        if self._native:
            return self._native.risk_gross_exposure_py(quantities, prices)
        # Python fallback
        return sum(q * p for q, p in zip(quantities, prices))
    
    def match_orders(self, buy_qty: int, asks: list[int]) -> tuple[int, int]:
        """
        Match buy orders against asks.
        
        Args:
            buy_qty: Quantity to buy
            asks: List of ask quantities
            
        Returns:
            Tuple of (filled, remaining)
        """
        if self._native:
            return self._native.match_orders_py(buy_qty, asks)
        # Python fallback
        remaining = buy_qty
        filled = 0
        for ask in asks:
            if remaining == 0:
                break
            take = min(remaining, ask)
            filled += take
            remaining -= take
        return (filled, remaining)
    
    def normalize_market_events(self, events: list[tuple[float, float]]) -> list[tuple[float, float]]:
        """
        Normalize market events (deduplicate and sort).
        
        Args:
            events: List of (timestamp, value) tuples
            
        Returns:
            Normalized and deduplicated events
        """
        if self._native:
            return self._native.normalize_market_events(events)
        # Python fallback
        deduped = sorted(events, key=lambda x: x[0])
        seen = set()
        result = []
        for event in deduped:
            if event[0] not in seen:
                seen.add(event[0])
                result.append(event)
        return result
    
    def serialize_event_json(self, event_data: list[tuple[str, str]]) -> str:
        """
        Serialize event data to JSON.
        
        Args:
            event_data: List of (key, value) tuples
            
        Returns:
            JSON string
        """
        if self._native:
            return self._native.serialize_event_json(event_data)
        # Python fallback
        import json
        return json.dumps(dict(event_data))


# Global bridge instance
_rust_bridge: Optional[RustBridge] = None


def get_rust_bridge() -> RustBridge:
    """
    Get the global Rust bridge instance.
    
    Returns:
        RustBridge instance
    """
    global _rust_bridge
    if _rust_bridge is None:
        _rust_bridge = RustBridge()
    return _rust_bridge


def rust_available() -> bool:
    """
    Check if Rust native implementation is available.
    
    Returns:
        True if Rust is available, False otherwise
    """
    return RUST_AVAILABLE


__all__ = [
    'RustBridge',
    'get_rust_bridge',
    'rust_available',
]