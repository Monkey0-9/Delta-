"""
Event-driven microstructure backtester for institutional research.

This implements production-grade backtesting:
- Event-driven architecture
- Order book simulation
- Execution modeling
- Transaction cost modeling
- Performance attribution
- Reproducibility guarantees
"""
from __future__ import annotations

from .event import Event, EventType, OrderEvent, FillEvent, MarketDataEvent
from .backtester import MicrostructureBacktester, BacktestConfig, BacktestResult
from .strategy import Strategy, StrategySignal
from .execution import ExecutionModel, Order
from .portfolio import Portfolio, Position
from .performance import PerformanceMetrics, Attribution

__all__ = [
    # Events
    "Event",
    "EventType",
    "OrderEvent",
    "FillEvent",
    "MarketDataEvent",
    
    # Backtester
    "MicrostructureBacktester",
    "BacktestConfig",
    "BacktestResult",
    
    # Strategy
    "Strategy",
    "StrategySignal",
    
    # Execution
    "ExecutionModel",
    "Order",
    
    # Portfolio
    "Portfolio",
    "Position",
    
    # Performance
    "PerformanceMetrics",
    "Attribution",
]