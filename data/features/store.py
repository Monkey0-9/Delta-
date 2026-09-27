"""Versioned Feature Store implementation.

W98: Implements versioned feature storage with indexing by
(Symbol, t_available) to prevent data leakage in backtesting.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4


class FeatureDataType(StrEnum):
    """Data types for features."""
    FLOAT = "float"
    DECIMAL = "decimal"
    INTEGER = "integer"
    BOOLEAN = "boolean"
    STRING = "string"
    VECTOR = "vector"


@dataclass(frozen=True, slots=True)
class FeatureKey:
    """Unique key for a feature."""
    symbol: str
    feature_name: str
    timestamp: datetime
    
    def __hash__(self) -> int:
        return hash((self.symbol.upper(), self.feature_name, self.timestamp))
    
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, FeatureKey):
            return False
        return (
            self.symbol.upper() == other.symbol.upper()
            and self.feature_name == other.feature_name
            and self.timestamp == other.timestamp
        )


@dataclass(frozen=True, slots=True)
class FeatureVersion:
    """
    Versioned feature with metadata.
    
    Tracks feature lineage for reproducibility and audit trails.
    """
    version_id: UUID = field(default_factory=uuid4)
    key: FeatureKey = field(default_factory=lambda: FeatureKey("", "", datetime.now(timezone.utc)))
    value: Any = None
    data_type: FeatureDataType = FeatureDataType.FLOAT
    
    # Versioning metadata
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    git_sha: str = ""
    dataset_hash: str = ""
    computation_params: dict[str, Any] = field(default_factory=dict)
    
    # Quality metadata
    quality_score: float = 1.0  # 0.0 to 1.0
    is_outlier: bool = False
    missing: bool = False
    
    # Source tracking
    source: str = "unknown"
    pipeline_version: str = "1.0"


class FeatureStore:
    """
    Versioned feature store with (Symbol, t_available) indexing.
    
    Prevents data leakage by ensuring features are indexed by their
    availability timestamp, not event timestamp.
    """
    
    def __init__(self) -> None:
        self._features: dict[FeatureKey, FeatureVersion] = {}
        self._symbol_index: dict[str, set[FeatureKey]] = {}
        self._feature_name_index: dict[str, set[FeatureKey]] = {}
        self._time_index: dict[datetime, set[FeatureKey]] = {}
    
    def put(self, version: FeatureVersion) -> None:
        """Store a feature version."""
        key = version.key
        
        self._features[key] = version
        
        # Update indices
        symbol = key.symbol.upper()
        if symbol not in self._symbol_index:
            self._symbol_index[symbol] = set()
        self._symbol_index[symbol].add(key)
        
        feature_name = key.feature_name
        if feature_name not in self._feature_name_index:
            self._feature_name_index[feature_name] = set()
        self._feature_name_index[feature_name].add(key)
        
        timestamp = key.timestamp
        if timestamp not in self._time_index:
            self._time_index[timestamp] = set()
        self._time_index[timestamp].add(key)
    
    def get(self, key: FeatureKey) -> FeatureVersion | None:
        """Get a specific feature version."""
        return self._features.get(key)
    
    def get_symbol_features(
        self,
        symbol: str,
        feature_names: list[str] | None = None,
        as_of: datetime | None = None
    ) -> dict[str, FeatureVersion]:
        """
        Get all features for a symbol.
        
        Args:
            symbol: Asset symbol
            feature_names: Optional list of specific feature names
            as_of: Optional timestamp to get features as of this date
        
        Returns:
            Dictionary mapping feature_name -> FeatureVersion
        """
        symbol = symbol.upper()
        if symbol not in self._symbol_index:
            return {}
        
        keys = self._symbol_index[symbol]
        
        if feature_names:
            keys = {k for k in keys if k.feature_name in feature_names}
        
        if as_of is not None:
            keys = {k for k in keys if k.timestamp <= as_of}
        
        result: dict[str, FeatureVersion] = {}
        for key in keys:
            version = self._features.get(key)
            if version:
                result[key.feature_name] = version
        
        return result
    
    def get_feature_values(
        self,
        symbols: list[str],
        feature_name: str,
        as_of: datetime
    ) -> dict[str, Any]:
        """
        Get feature values for multiple symbols at a specific time.
        
        Used for cross-sectional operations like neutralization.
        """
        feature_name_idx = self._feature_name_index.get(feature_name, set())
        
        result: dict[str, Any] = {}
        for symbol in symbols:
            symbol = symbol.upper()
            
            # Find the most recent feature value for this symbol
            candidates = [
                k for k in feature_name_idx
                if k.symbol.upper() == symbol and k.timestamp <= as_of
            ]
            
            if candidates:
                # Get the most recent
                latest_key = max(candidates, key=lambda k: k.timestamp)
                version = self._features.get(latest_key)
                if version and not version.missing:
                    result[symbol] = version.value
        
        return result
    
    def get_cross_section(
        self,
        symbols: list[str],
        feature_names: list[str],
        as_of: datetime
    ) -> dict[str, dict[str, Any]]:
        """
        Get cross-sectional feature matrix.
        
        Returns dict[symbol][feature_name] -> value
        """
        result: dict[str, dict[str, Any]] = {}
        
        for symbol in symbols:
            symbol_features = self.get_symbol_features(symbol, feature_names, as_of)
            result[symbol] = {
                name: version.value
                for name, version in symbol_features.items()
                if not version.missing
            }
        
        return result
    
    def get_time_series(
        self,
        symbol: str,
        feature_name: str,
        start_date: datetime,
        end_date: datetime
    ) -> list[tuple[datetime, Any]]:
        """
        Get time series for a symbol and feature.
        
        Returns list of (timestamp, value) tuples.
        """
        symbol = symbol.upper()
        if symbol not in self._symbol_index:
            return []
        
        keys = [
            k for k in self._symbol_index[symbol]
            if k.feature_name == feature_name
            and start_date <= k.timestamp <= end_date
        ]
        
        sorted_keys = sorted(keys, key=lambda k: k.timestamp)
        
        result = []
        for key in sorted_keys:
            version = self._features.get(key)
            if version and not version.missing:
                result.append((key.timestamp, version.value))
        
        return result
    
    def delete_symbol(self, symbol: str) -> None:
        """Delete all features for a symbol."""
        symbol = symbol.upper()
        if symbol not in self._symbol_index:
            return
        
        keys = self._symbol_index[symbol]
        
        for key in keys:
            # Remove from main store
            self._features.pop(key, None)
            
            # Remove from feature name index
            if key.feature_name in self._feature_name_index:
                self._feature_name_index[key.feature_name].discard(key)
            
            # Remove from time index
            if key.timestamp in self._time_index:
                self._time_index[key.timestamp].discard(key)
        
        # Remove symbol index entry
        del self._symbol_index[symbol]
    
    def get_statistics(self) -> dict[str, Any]:
        """Get feature store statistics."""
        return {
            "total_features": len(self._features),
            "unique_symbols": len(self._symbol_index),
            "unique_feature_names": len(self._feature_name_index),
            "unique_timestamps": len(self._time_index),
            "avg_features_per_symbol": (
                sum(len(keys) for keys in self._symbol_index.values())
                / len(self._symbol_index) if self._symbol_index else 0
            ),
        }
