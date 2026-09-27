"""Real Market Data Infrastructure - W94 Foundation

This module provides the foundation for real market data ingestion,
point-in-time storage, and feature engineering to replace demo_candidates().
"""

from .adapters import MarketDataAdapter, RealTimeAdapter, HistoricalAdapter
from .pit_store import PointInTimeStore
from .quality import DataQualityChecker
from .feature_engine import FeatureEngine
from .signal_generator import SignalGenerator

__all__ = [
    "MarketDataAdapter",
    "RealTimeAdapter", 
    "HistoricalAdapter",
    "PointInTimeStore",
    "DataQualityChecker",
    "FeatureEngine",
    "SignalGenerator",
]
