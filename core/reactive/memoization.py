"""Memoization cache for reactive graph computation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import Lock
from typing import Any
from uuid import UUID


@dataclass(frozen=True, slots=True)
class CacheEntry:
    """Cache entry with metadata."""
    value: Any
    computed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    hit_count: int = 0
    size_bytes: int = 0


class MemoizationCache:
    """
    Thread-safe memoization cache for reactive graph.
    
    Implements automatic memoization with hit tracking and
    size-based eviction policies.
    """
    
    def __init__(self, max_size_mb: int = 100) -> None:
        self._cache: dict[UUID, CacheEntry] = {}
        self._max_size_bytes = max_size_mb * 1024 * 1024
        self._current_size_bytes = 0
        self._lock = Lock()
        self._hit_count = 0
        self._miss_count = 0
    
    def get(self, key: UUID) -> Any | None:
        """Get value from cache."""
        with self._lock:
            entry = self._cache.get(key)
            
            if entry is None:
                self._miss_count += 1
                return None
            
            # Update hit count
            self._hit_count += 1
            self._cache[key] = CacheEntry(
                value=entry.value,
                computed_at=entry.computed_at,
                hit_count=entry.hit_count + 1,
                size_bytes=entry.size_bytes
            )
            
            return entry.value
    
    def put(self, key: UUID, value: Any, size_bytes: int = 0) -> None:
        """Put value into cache with optional size hint."""
        with self._lock:
            # Check if we need to evict
            if size_bytes > 0 and self._current_size_bytes + size_bytes > self._max_size_bytes:
                self._evict_lru()
            
            entry = CacheEntry(
                value=value,
                size_bytes=size_bytes
            )
            
            # Update size tracking
            if key in self._cache:
                self._current_size_bytes -= self._cache[key].size_bytes
            
            self._cache[key] = entry
            self._current_size_bytes += size_bytes
    
    def invalidate(self, key: UUID) -> None:
        """Invalidate a specific cache entry."""
        with self._lock:
            if key in self._cache:
                self._current_size_bytes -= self._cache[key].size_bytes
                del self._cache[key]
    
    def clear(self) -> None:
        """Clear all cache entries."""
        with self._lock:
            self._cache.clear()
            self._current_size_bytes = 0
    
    def _evict_lru(self) -> None:
        """Evict least recently used entries."""
        if not self._cache:
            return
        
        # Sort by hit count (ascending) and computed_at (ascending)
        sorted_entries = sorted(
            self._cache.items(),
            key=lambda x: (x[1].hit_count, x[1].computed_at)
        )
        
        # Evict entries until we have space
        for key, entry in sorted_entries:
            self._current_size_bytes -= entry.size_bytes
            del self._cache[key]
            
            if self._current_size_bytes < self._max_size_bytes * 0.8:  # Target 80% utilization
                break
    
    def get_statistics(self) -> dict[str, Any]:
        """Get cache statistics."""
        with self._lock:
            total_requests = self._hit_count + self._miss_count
            hit_rate = self._hit_count / total_requests if total_requests > 0 else 0
            
            return {
                "entries": len(self._cache),
                "hit_count": self._hit_count,
                "miss_count": self._miss_count,
                "hit_rate": hit_rate,
                "current_size_bytes": self._current_size_bytes,
                "max_size_bytes": self._max_size_bytes,
                "utilization": self._current_size_bytes / self._max_size_bytes if self._max_size_bytes > 0 else 0,
            }
