"""
Tri-tier resilient market data engine
"""
from data.base_provider import Bar, BaseDataProvider, NewsItem, Quote
from data.cache import DataCache

try:
    from data.router import DataRouter
except ImportError:  # router needs the optional `delta.*` namespace
    DataRouter = None  # type: ignore[assignment, misc]

__all__ = ["DataRouter", "DataCache", "BaseDataProvider", "Quote", "Bar", "NewsItem"]
