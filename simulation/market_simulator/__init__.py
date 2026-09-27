"""
Institutional-grade market simulator with L2/L3 order book and matching engine.

This module provides production-quality market simulation including:
- L2/L3 order book with price-time priority
- Matching engine with FIFO execution
- Queue position modeling
- Realistic latency distributions
- Market impact modeling
- Fee/rebate structures
- Adverse selection modeling
"""
from __future__ import annotations

from .order_book import OrderBook, OrderBookLevel, LimitOrder, MarketOrder, OrderSide
from .matching_engine import MatchingEngine, ExecutionResult, FillEvent, OrderType, OrderStatus
from .queue_position import QueuePositionCalculator, QueuePositionInfo
from .latency_model import LatencyModel, LatencyDistribution, LatencyMeasurement
from .market_impact import MarketImpactModel, AlmgrenChrissImpact, KyleLambdaImpact, ImpactModelType, ImpactParameters, ImpactEstimate
from .fee_structure import FeeStructure, MakerTakerFees, ExchangeFees, FeeSchedule, FeeCalculation, FeeOptimizer, FeeModel
from .adverse_selection import AdverseSelectionModel, MarketCondition
from .integrated_simulator import IntegratedMarketSimulator, SimulationResult

__all__ = [
    "OrderBook",
    "OrderBookLevel",
    "LimitOrder",
    "MarketOrder",
    "OrderSide",
    "MatchingEngine",
    "ExecutionResult",
    "FillEvent",
    "OrderType",
    "OrderStatus",
    "QueuePositionCalculator",
    "QueuePositionInfo",
    "LatencyModel",
    "LatencyDistribution",
    "LatencyMeasurement",
    "MarketImpactModel",
    "AlmgrenChrissImpact",
    "KyleLambdaImpact",
    "ImpactModelType",
    "ImpactParameters",
    "ImpactEstimate",
    "FeeStructure",
    "MakerTakerFees",
    "ExchangeFees",
    "FeeSchedule",
    "FeeCalculation",
    "FeeOptimizer",
    "FeeModel",
    "AdverseSelectionModel",
    "MarketCondition",
    "IntegratedMarketSimulator",
    "SimulationResult",
]