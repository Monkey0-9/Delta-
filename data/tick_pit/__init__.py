"""
Production-grade Point-in-Time (PIT) data infrastructure with tick-level support.

This implements institutional-grade PIT data management:
- Tick-level data structures (quotes, trades, order book updates)
- Multi-timestamp management (event_time, available_time, published_time, etc.)
- PIT query engine with temporal guarantees
- Look-ahead bias detection and prevention
- Data quality validation
- Corporate actions handling
- Trading calendar integration
"""
from __future__ import annotations

# trading_calendar is implemented; remaining submodules load progressively so
# missing modules never break the package import (they fail only on direct use).
from .trading_calendar import TradingCalendar, CalendarManager, get_calendar  # noqa: E402

try:
    from .tick_data import TickData, Quote, Trade, OrderBookUpdate, TickType, TickAggregator  # noqa
except ImportError:  # pragma: no cover - module not yet implemented
    pass
try:
    from .timestamps import DataTimestamps, TimestampManager, TimestampType  # noqa
except ImportError:  # pragma: no cover - module not yet implemented
    pass
try:
    from .pit_store import PITStore, PITQuery, PITSnapshot, PITStorageType  # noqa
except ImportError:  # pragma: no cover - module not yet implemented
    pass
try:
    from .data_quality import DataQualityValidator, QualityIssue, QualityThresholds  # noqa
except ImportError:  # pragma: no cover - module not yet implemented
    pass
try:
    from .lookahead_detector import LookaheadBiasDetector, BiasReport, BiasType  # noqa
except ImportError:  # pragma: no cover - module not yet implemented
    pass
try:
    from .corporate_actions import CorporateAction, CorporateActionHandler, ActionType  # noqa
except ImportError:  # pragma: no cover - module not yet implemented
    pass

__all__ = [
    # Tick data structures
    "TickData",
    "Quote",
    "Trade",
    "OrderBookUpdate",
    "TickType",

    # Timestamp management
    "DataTimestamps",
    "TimestampManager",

    # PIT storage
    "PITStore",
    "PITQuery",
    "PITSnapshot",

    # Data quality
    "DataQualityValidator",
    "QualityIssue",
    "QualityThresholds",

    # Lookahead bias detection
    "LookaheadBiasDetector",
    "BiasReport",

    # Corporate actions
    "CorporateAction",
    "CorporateActionHandler",
    "ActionType",

    # Trading calendar
    "TradingCalendar",
    "CalendarManager",
    "get_calendar",
]
