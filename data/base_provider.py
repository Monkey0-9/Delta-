"""
Abstract base interface for data providers
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import pandas as pd


class DataType(Enum):
    """Types of data a provider can serve"""
    QUOTE = "quote"
    BARS = "bars"
    FUNDAMENTALS = "fundamentals"
    NEWS = "news"
    MACRO = "macro"
    OPTIONS = "options"


class DataQuality(Enum):
    """Data quality indicators"""
    LIVE = "live"
    DELAYED = "delayed"
    CACHED = "cached"
    SYNTHETIC = "synthetic"


@dataclass
class Quote:
    """Real-time quote data"""
    symbol: str
    bid: float
    ask: float
    bid_size: int
    ask_size: int
    last: float
    volume: int
    timestamp: datetime
    quality: DataQuality = DataQuality.LIVE


@dataclass
class Bar:
    """OHLCV bar data"""
    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    quality: DataQuality = DataQuality.LIVE


@dataclass
class NewsItem:
    """News article data"""
    title: str
    url: str
    source: str
    published_at: datetime
    symbols: List[str]
    sentiment: float  # -1.0 to 1.0
    summary: Optional[str] = None


@dataclass
class MacroSeries:
    """Macro economic time series"""
    series_id: str
    name: str
    data: pd.DataFrame
    last_updated: datetime
    quality: DataQuality = DataQuality.LIVE


class BaseDataProvider(ABC):
    """Abstract base class for all data providers"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.provider_name = config.get("name", "unknown")
        self.enabled = config.get("enabled", True)
        self._initialized = False
        self._rate_limit_remaining: Optional[int] = None
    
    @abstractmethod
    async def initialize(self) -> bool:
        """Initialize the data provider"""
        pass
    
    @abstractmethod
    async def get_quote(self, symbol: str) -> Optional[Quote]:
        """Get real-time quote for a symbol"""
        pass
    
    @abstractmethod
    async def get_bars(self, symbol: str, timeframe: str, 
                      start: datetime, end: datetime) -> List[Bar]:
        """Get historical bars for a symbol"""
        pass
    
    @abstractmethod
    async def get_news(self, symbol: str, limit: int = 10) -> List[NewsItem]:
        """Get news for a symbol"""
        pass
    
    @abstractmethod
    def supports_data_type(self, data_type: DataType) -> bool:
        """Check if provider supports a specific data type"""
        pass
    
    def is_initialized(self) -> bool:
        """Check if provider is initialized"""
        return self._initialized
    
    def is_enabled(self) -> bool:
        """Check if provider is enabled"""
        return self.enabled
    
    def get_rate_limit_remaining(self) -> Optional[int]:
        """Get remaining API calls for rate limiting"""
        return self._rate_limit_remaining
    
    async def health_check(self) -> bool:
        """Perform a health check on the provider"""
        try:
            quote = await self.get_quote("AAPL")
            return quote is not None
        except Exception:
            return False
    
    def validate_config(self) -> bool:
        """Validate the provider configuration"""
        return "name" in self.config
    
    def get_provider_name(self) -> str:
        """Get the provider name"""
        return self.provider_name


class MarketDataProvider(BaseDataProvider):
    """Base class for market data providers (quotes, bars, news)"""
    
    def supports_data_type(self, data_type: DataType) -> bool:
        """Market data providers typically support quotes, bars, and news"""
        return data_type in [DataType.QUOTE, DataType.BARS, DataType.NEWS]


class MacroDataProvider(BaseDataProvider):
    """Base class for macro economic data providers"""
    
    def supports_data_type(self, data_type: DataType) -> bool:
        """Macro data providers support macro series"""
        return data_type == DataType.MACRO
    
    @abstractmethod
    async def get_macro_series(self, series_id: str) -> Optional[MacroSeries]:
        """Get macro economic series"""
        pass


class FailoverProvider(BaseDataProvider):
    """Base class for providers with failover capabilities"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.fallback_providers: List[BaseDataProvider] = []
        self.current_provider_index = 0
    
    def add_fallback_provider(self, provider: BaseDataProvider) -> None:
        """Add a fallback provider"""
        self.fallback_providers.append(provider)
    
    async def get_quote_with_fallback(self, symbol: str) -> Optional[Quote]:
        """Get quote with automatic failover"""
        providers = [self] + self.fallback_providers
        
        for i, provider in enumerate(providers):
            try:
                if provider.is_enabled() and provider.is_initialized():
                    quote = await provider.get_quote(symbol)
                    if quote:
                        return quote
            except Exception as e:
                print(f"Provider {i} failed: {e}")
                continue
        
        return None
    
    async def get_bars_with_fallback(self, symbol: str, timeframe: str,
                                     start: datetime, end: datetime) -> List[Bar]:
        """Get bars with automatic failover"""
        providers = [self] + self.fallback_providers
        
        for i, provider in enumerate(providers):
            try:
                if provider.is_enabled() and provider.is_initialized():
                    bars = await provider.get_bars(symbol, timeframe, start, end)
                    if bars:
                        return bars
            except Exception as e:
                print(f"Provider {i} failed: {e}")
                continue
        
        return []
