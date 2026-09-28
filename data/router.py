"""
Fail-soft data router with tri-tier fallback architecture
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from delta.data.base_provider import (
    BaseDataProvider, Quote, Bar, NewsItem, DataType, DataQuality
)
from delta.data.cache import QuoteCache, BarsCache, NewsCache, MacroCache
from delta.core.registry import data_provider_registry
from delta.core.config import Config, DataProviderConfig

logger = logging.getLogger(__name__)


class DataRouter:
    """Fail-soft data router with automatic fallback"""
    
    def __init__(self, config: Config):
        self.config = config
        self.providers: Dict[str, BaseDataProvider] = {}
        self.primary_provider: Optional[BaseDataProvider] = None
        self.fallback_providers: List[BaseDataProvider] = []
        
        # Caches
        self.quote_cache = QuoteCache()
        self.bars_cache = BarsCache()
        self.news_cache = NewsCache()
        self.macro_cache = MacroCache()
        
        # Synthetic offline generator: OFF by default. Producing fake quotes
        # labeled SYNTHETIC without explicit opt-in is a trading-integrity
        # violation — call enable_synthetic_offline() only for offline
        # research/simulation, never for live pricing or execution.
        self.synthetic_enabled = False

    def enable_synthetic_offline(self) -> None:
        """Explicit opt-in to labeled synthetic fallback (research/sim only)."""
        self.synthetic_enabled = True
    
    async def initialize(self) -> None:
        """Initialize all configured data providers"""
        for provider_config in self.config.data_providers:
            if not provider_config.enabled:
                continue
            
            try:
                provider = await self._create_provider(provider_config)
                if provider:
                    self.providers[provider_config.name] = provider
                    logger.info(f"Initialized data provider: {provider_config.name}")
            except Exception as e:
                logger.error(f"Failed to initialize provider {provider_config.name}: {e}")
        
        # Set primary provider
        if self.config.data_providers:
            primary_name = self.config.data_providers[0].name
            if primary_name in self.providers:
                self.primary_provider = self.providers[primary_name]
                # Remaining providers become fallbacks
                self.fallback_providers = [
                    self.providers[name] for name in self.config.data_providers[1:].name
                    if name in self.providers
                ]
    
    async def _create_provider(self, provider_config: DataProviderConfig) -> Optional[BaseDataProvider]:
        """Create a provider instance from configuration"""
        provider_type = provider_config.provider
        
        provider_class = data_provider_registry.get_provider_class(provider_type)
        if not provider_class:
            logger.error(f"Provider class not found: {provider_type}")
            return None
        
        provider_config_dict = {
            "name": provider_config.name,
            **provider_config.params
        }
        
        provider = provider_class(provider_config_dict)
        if await provider.initialize():
            return provider
        
        return None
    
    async def get_quote(self, symbol: str, force_refresh: bool = False) -> Optional[Quote]:
        """Get quote with automatic fallback and caching"""
        # Check cache first
        if not force_refresh:
            cached = self.quote_cache.get_quote(symbol)
            if cached:
                return cached
        
        # Try primary provider
        if self.primary_provider:
            try:
                quote = await self.primary_provider.get_quote(symbol)
                if quote:
                    self.quote_cache.set_quote(symbol, quote)
                    return quote
            except Exception as e:
                logger.warning(f"Primary provider failed for quote {symbol}: {e}")
        
        # Try fallback providers
        for provider in self.fallback_providers:
            try:
                if provider.supports_data_type(DataType.QUOTE):
                    quote = await provider.get_quote(symbol)
                    if quote:
                        self.quote_cache.set_quote(symbol, quote, quality="delayed")
                        return quote
            except Exception as e:
                logger.warning(f"Fallback provider failed for quote {symbol}: {e}")
        
        # Fallback to synthetic data if enabled
        if self.synthetic_enabled:
            return self._generate_synthetic_quote(symbol)
        
        return None
    
    async def get_bars(self, symbol: str, timeframe: str, 
                      start: datetime, end: datetime,
                      force_refresh: bool = False) -> List[Bar]:
        """Get historical bars with automatic fallback and caching"""
        cache_key = f"{symbol}_{timeframe}_{start.isoformat()}_{end.isoformat()}"
        
        # Check cache first
        if not force_refresh:
            cached = self.bars_cache.get_bars(symbol, timeframe)
            if cached:
                return cached
        
        # Try primary provider
        if self.primary_provider:
            try:
                bars = await self.primary_provider.get_bars(symbol, timeframe, start, end)
                if bars:
                    self.bars_cache.set_bars(symbol, timeframe, bars)
                    return bars
            except Exception as e:
                logger.warning(f"Primary provider failed for bars {symbol}: {e}")
        
        # Try fallback providers
        for provider in self.fallback_providers:
            try:
                if provider.supports_data_type(DataType.BARS):
                    bars = await provider.get_bars(symbol, timeframe, start, end)
                    if bars:
                        self.bars_cache.set_bars(symbol, timeframe, bars, quality="delayed")
                        return bars
            except Exception as e:
                logger.warning(f"Fallback provider failed for bars {symbol}: {e}")
        
        # Fallback to synthetic data if enabled
        if self.synthetic_enabled:
            return self._generate_synthetic_bars(symbol, timeframe, start, end)
        
        return []
    
    async def get_news(self, symbol: str, limit: int = 10,
                      force_refresh: bool = False) -> List[NewsItem]:
        """Get news with automatic fallback and caching"""
        # Check cache first
        if not force_refresh:
            cached = self.news_cache.get_news(symbol)
            if cached:
                return cached[:limit]
        
        # Try primary provider
        if self.primary_provider:
            try:
                news = await self.primary_provider.get_news(symbol, limit)
                if news:
                    self.news_cache.set_news(symbol, news)
                    return news[:limit]
            except Exception as e:
                logger.warning(f"Primary provider failed for news {symbol}: {e}")
        
        # Try fallback providers
        for provider in self.fallback_providers:
            try:
                if provider.supports_data_type(DataType.NEWS):
                    news = await provider.get_news(symbol, limit)
                    if news:
                        self.news_cache.set_news(symbol, news, quality="delayed")
                        return news[:limit]
            except Exception as e:
                logger.warning(f"Fallback provider failed for news {symbol}: {e}")
        
        return []
    
    def _generate_synthetic_quote(self, symbol: str) -> Quote:
        """Generate synthetic quote for offline mode"""
        import random
        base_price = random.uniform(50, 200)
        spread = base_price * 0.001
        
        return Quote(
            symbol=symbol,
            bid=base_price - spread,
            ask=base_price + spread,
            bid_size=random.randint(100, 1000),
            ask_size=random.randint(100, 1000),
            last=base_price,
            volume=random.randint(10000, 1000000),
            timestamp=datetime.utcnow(),
            quality=DataQuality.SYNTHETIC
        )
    
    def _generate_synthetic_bars(self, symbol: str, timeframe: str,
                                 start: datetime, end: datetime) -> List[Bar]:
        """Generate synthetic bars for offline mode"""
        import random
        from datetime import timedelta
        
        bars = []
        current_time = start
        base_price = random.uniform(50, 200)
        
        while current_time < end:
            volatility = base_price * 0.02
            open_price = base_price + random.uniform(-volatility, volatility)
            close_price = base_price + random.uniform(-volatility, volatility)
            high_price = max(open_price, close_price) + random.uniform(0, volatility * 0.5)
            low_price = min(open_price, close_price) - random.uniform(0, volatility * 0.5)
            
            bar = Bar(
                symbol=symbol,
                timestamp=current_time,
                open=open_price,
                high=high_price,
                low=low_price,
                close=close_price,
                volume=random.randint(10000, 1000000),
                quality=DataQuality.SYNTHETIC
            )
            bars.append(bar)
            
            base_price = close_price
            current_time += timedelta(hours=1)  # 1-hour bars
        
        return bars
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get statistics for all caches"""
        return {
            "quote_cache": self.quote_cache.get_stats(),
            "bars_cache": self.bars_cache.get_stats(),
            "news_cache": self.news_cache.get_stats(),
            "macro_cache": self.macro_cache.get_stats()
        }
    
    def clear_caches(self) -> None:
        """Clear all caches"""
        self.quote_cache.clear()
        self.bars_cache.clear()
        self.news_cache.clear()
        self.macro_cache.clear()
        logger.info("All data caches cleared")
    
    def cleanup_expired_cache_entries(self) -> int:
        """Clean up expired cache entries"""
        total = 0
        total += self.quote_cache.cleanup_expired()
        total += self.bars_cache.cleanup_expired()
        total += self.news_cache.cleanup_expired()
        total += self.macro_cache.cleanup_expired()
        return total
    
    async def health_check(self) -> Dict[str, bool]:
        """Health check on all providers"""
        results = {}
        for name, provider in self.providers.items():
            results[name] = await provider.health_check()
        return results
