"""Realistic Backtesting Module - W96

Implements institutional-grade backtesting with microstructure simulation,
market impact modeling, and statistical validation.
"""

from .realistic import (
    RealisticBacktester,
    MarketImpactCalculator,
    OrderBookSimulator,
    LatencySimulator,
    StatisticalValidator,
    Order,
    Fill,
    OrderBook,
    BacktestResult,
    OrderType,
    OrderSide,
    FillType,
    MarketImpactModel,
)

__all__ = [
    "RealisticBacktester",
    "MarketImpactCalculator",
    "OrderBookSimulator",
    "LatencySimulator",
    "StatisticalValidator",
    "Order",
    "Fill",
    "OrderBook",
    "BacktestResult",
    "OrderType",
    "OrderSide",
    "FillType",
    "MarketImpactModel",
]
