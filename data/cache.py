"""
In-memory LRU cache for time-series data with staleness tracking
"""

import time
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from datetime import datetime, timedelta
from collections import OrderedDict
import logging

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """Cache entry with metadata"""
    data: Any
    timestamp: datetime
    ttl_seconds: int
    quality: str = "live"
    
    def is_expired(self) -> bool:
        """Check if entry is expired"""
        return datetime.utcnow() > self.timestamp + timedelta(seconds=self.ttl_seconds)
    
    def age_seconds(self) -> float:
        """Get age of entry in seconds"""
        return (datetime.utcnow() - self.timestamp).total_seconds()


class DataCache:
    """In-memory LRU cache for market data"""
    
    def __init__(self, max_size: int = 1000, default_ttl: int = 60):
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._hits = 0
        self._misses = 0
    
    def _generate_key(self, category: str, identifier: str, **kwargs) -> str:
        """Generate a cache key"""
        key_parts = [category, identifier]
        for k, v in sorted(kwargs.items()):
            key_parts.append(f"{k}={v}")
        return ":".join(key_parts)
    
    def get(self, category: str, identifier: str, **kwargs) -> Optional[Any]:
        """Get data from cache"""
        key = self._generate_key(category, identifier, **kwargs)
        
        if key not in self._cache:
            self._misses += 1
            return None
        
        entry = self._cache[key]
        
        # Check if expired
        if entry.is_expired():
            del self._cache[key]
            self._misses += 1
            logger.debug(f"Cache entry expired: {key}")
            return None
        
        # Move to end (most recently used)
        self._cache.move_to_end(key)
        self._hits += 1
        
        logger.debug(f"Cache hit: {key} (age: {entry.age_seconds():.1f}s)")
        return entry.data
    
    def set(self, category: str, identifier: str, data: Any, 
            ttl: Optional[int] = None, quality: str = "live", **kwargs) -> None:
        """Set data in cache"""
        key = self._generate_key(category, identifier, **kwargs)
        ttl = ttl or self.default_ttl
        
        entry = CacheEntry(
            data=data,
            timestamp=datetime.utcnow(),
            ttl_seconds=ttl,
            quality=quality
        )
        
        # Add or update entry
        self._cache[key] = entry
        self._cache.move_to_end(key)
        
        # Enforce size limit
        if len(self._cache) > self.max_size:
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]
            logger.debug(f"Evicted oldest cache entry: {oldest_key}")
        
        logger.debug(f"Cache set: {key} (ttl: {ttl}s)")
    
    def invalidate(self, category: str, identifier: str, **kwargs) -> bool:
        """Invalidate a specific cache entry"""
        key = self._generate_key(category, identifier, **kwargs)
        if key in self._cache:
            del self._cache[key]
            logger.debug(f"Cache invalidated: {key}")
            return True
        return False
    
    def invalidate_category(self, category: str) -> int:
        """Invalidate all entries in a category"""
        keys_to_delete = [k for k in self._cache.keys() if k.startswith(category + ":")]
        for key in keys_to_delete:
            del self._cache[key]
        logger.debug(f"Invalidated {len(keys_to_delete)} entries in category: {category}")
        return len(keys_to_delete)
    
    def clear(self) -> None:
        """Clear all cache entries"""
        self._cache.clear()
        self._hits = 0
        self._misses = 0
        logger.info("Cache cleared")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        total_requests = self._hits + self._misses
        hit_rate = self._hits / total_requests if total_requests > 0 else 0
        
        return {
            "size": len(self._cache),
            "max_size": self.max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": hit_rate,
            "entries": [
                {
                    "key": key,
                    "age_seconds": entry.age_seconds(),
                    "quality": entry.quality,
                    "expired": entry.is_expired()
                }
                for key, entry in list(self._cache.items())[-10:]  # Last 10 entries
            ]
        }
    
    def cleanup_expired(self) -> int:
        """Remove all expired entries"""
        keys_to_delete = [k for k, v in self._cache.items() if v.is_expired()]
        for key in keys_to_delete:
            del self._cache[key]
        
        if keys_to_delete:
            logger.debug(f"Cleaned up {len(keys_to_delete)} expired entries")
        
        return len(keys_to_delete)


class QuoteCache(DataCache):
    """Specialized cache for quote data"""
    
    def __init__(self, max_size: int = 500, default_ttl: int = 5):
        super().__init__(max_size, default_ttl)
    
    def get_quote(self, symbol: str) -> Optional[Any]:
        """Get quote from cache"""
        return self.get("quote", symbol)
    
    def set_quote(self, symbol: str, quote: Any, ttl: Optional[int] = None) -> None:
        """Set quote in cache"""
        self.set("quote", symbol, quote, ttl=ttl)


class BarsCache(DataCache):
    """Specialized cache for historical bars"""
    
    def __init__(self, max_size: int = 2000, default_ttl: int = 3600):
        super().__init__(max_size, default_ttl)
    
    def get_bars(self, symbol: str, timeframe: str) -> Optional[Any]:
        """Get bars from cache"""
        return self.get("bars", symbol, timeframe=timeframe)
    
    def set_bars(self, symbol: str, timeframe: str, bars: Any, ttl: Optional[int] = None) -> None:
        """Set bars in cache"""
        self.set("bars", symbol, bars, ttl=ttl, timeframe=timeframe)


class NewsCache(DataCache):
    """Specialized cache for news data"""
    
    def __init__(self, max_size: int = 300, default_ttl: int = 300):
        super().__init__(max_size, default_ttl)
    
    def get_news(self, symbol: str) -> Optional[Any]:
        """Get news from cache"""
        return self.get("news", symbol)
    
    def set_news(self, symbol: str, news: Any, ttl: Optional[int] = None) -> None:
        """Set news in cache"""
        self.set("news", symbol, news, ttl=ttl)


class MacroCache(DataCache):
    """Specialized cache for macro data"""
    
    def __init__(self, max_size: int = 200, default_ttl: int = 86400):
        super().__init__(max_size, default_ttl)
    
    def get_series(self, series_id: str) -> Optional[Any]:
        """Get macro series from cache"""
        return self.get("macro", series_id)
    
    def set_series(self, series_id: str, data: Any, ttl: Optional[int] = None) -> None:
        """Set macro series in cache"""
        self.set("macro", series_id, data, ttl=ttl)
