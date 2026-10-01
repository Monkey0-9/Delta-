"""
Data quality validation for institutional data management.

This implements production-grade data quality checks:
- Price validation (negative, zero, extreme values)
- Volume validation (negative, zero, extreme values)
- Crossed market detection
- Out-of-order data detection
- Stale data detection
- Missing data detection
- Quality scoring
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple
import statistics

from .tick_data import Quote, Trade, TickData, TickType


class QualityIssue(Enum):
    """Quality issue types."""
    NEGATIVE_PRICE = "NEGATIVE_PRICE"
    ZERO_PRICE = "ZERO_PRICE"
    EXTREME_PRICE = "EXTREME_PRICE"
    NEGATIVE_VOLUME = "NEGATIVE_VOLUME"
    ZERO_VOLUME = "ZERO_VOLUME"
    EXTREME_VOLUME = "EXTREME_VOLUME"
    CROSSED_MARKET = "CROSSED_MARKET"
    OUT_OF_ORDER = "OUT_OF_ORDER"
    STALE_DATA = "STALE_DATA"
    MISSING_DATA = "MISSING_DATA"
    INVALID_SPREAD = "INVALID_SPREAD"
    SEQUENCE_GAP = "SEQUENCE_GAP"
    INCONSISTENT_TIMESTAMP = "INCONSISTENT_TIMESTAMP"


@dataclass(frozen=True, slots=True)
class QualityThresholds:
    """
    Quality validation thresholds.
    """
    min_price: float = 0.01
    max_price: float = 1_000_000.0
    max_price_change_pct: float = 50.0  # Max 50% change between ticks
    min_volume: float = 1.0
    max_volume: float = 1_000_000_000.0
    max_spread_bps: float = 1000.0  # Max 10% spread
    max_staleness_seconds: float = 3600.0  # Max 1 hour staleness
    max_sequence_gap: int = 1000  # Max sequence number gap
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "min_price": self.min_price,
            "max_price": self.max_price,
            "max_price_change_pct": self.max_price_change_pct,
            "min_volume": self.min_volume,
            "max_volume": self.max_volume,
            "max_spread_bps": self.max_spread_bps,
            "max_staleness_seconds": self.max_staleness_seconds,
            "max_sequence_gap": self.max_sequence_gap
        }


@dataclass
class QualityValidationResult:
    """
    Result of quality validation.
    """
    is_valid: bool
    quality_score: float  # 0-1
    issues: List[Tuple[QualityIssue, str]] = field(default_factory=list)
    warnings: List[Tuple[QualityIssue, str]] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "is_valid": self.is_valid,
            "quality_score": self.quality_score,
            "issues": [(issue.value, message) for issue, message in self.issues],
            "warnings": [(issue.value, message) for issue, message in self.warnings],
            "metadata": self.metadata
        }


class DataQualityValidator:
    """
    Validates data quality for institutional requirements.
    
    Features:
    - Real-time validation
    - Historical validation
    - Statistical validation
    - Customizable thresholds
    - Quality scoring
    """
    
    def __init__(self, thresholds: Optional[QualityThresholds] = None):
        """
        Initialize data quality validator.
        
        Args:
            thresholds: Quality validation thresholds
        """
        self.thresholds = thresholds or QualityThresholds()
        
        # Historical data for statistical validation
        self.price_history: Dict[str, List[float]] = {}
        self.volume_history: Dict[str, List[float]] = {}
        self.last_timestamps: Dict[str, datetime] = {}
        self.last_sequence_numbers: Dict[str, int] = {}
    
    def validate_tick(self, tick: TickData) -> QualityValidationResult:
        """
        Validate a single tick.
        
        Args:
            tick: Tick data to validate
            
        Returns:
            Quality validation result
        """
        issues = []
        warnings = []
        
        # Extract data based on type
        if isinstance(tick.data, Quote):
            quote_issues, quote_warnings = self._validate_quote(tick.data, tick.symbol)
            issues.extend(quote_issues)
            warnings.extend(quote_warnings)
            
        elif isinstance(tick.data, Trade):
            trade_issues, trade_warnings = self._validate_trade(tick.data, tick.symbol)
            issues.extend(trade_issues)
            warnings.extend(trade_warnings)
        
        # Validate timestamp
        timestamp_issues, timestamp_warnings = self._validate_timestamp(tick)
        issues.extend(timestamp_issues)
        warnings.extend(timestamp_warnings)
        
        # Validate sequence number
        sequence_issues, sequence_warnings = self._validate_sequence(tick)
        issues.extend(sequence_issues)
        warnings.extend(sequence_warnings)
        
        # Calculate quality score
        quality_score = self._calculate_quality_score(issues, warnings)
        
        # Determine validity
        is_valid = len(issues) == 0
        
        return QualityValidationResult(
            is_valid=is_valid,
            quality_score=quality_score,
            issues=issues,
            warnings=warnings,
            metadata={
                "tick_id": tick.tick_id,
                "tick_type": tick.tick_type.value,
                "symbol": tick.symbol,
                "timestamp": tick.timestamp.isoformat()
            }
        )
    
    def _validate_quote(self, quote: Quote, symbol: str) -> List[Tuple]:
        """Validate quote data."""
        issues = []
        warnings = []
        
        # Check bid price
        if quote.bid_price < 0:
            issues.append((QualityIssue.NEGATIVE_PRICE, f"Negative bid price: {quote.bid_price}"))
        elif quote.bid_price == 0:
            issues.append((QualityIssue.ZERO_PRICE, f"Zero bid price"))
        elif quote.bid_price < self.thresholds.min_price:
            issues.append((QualityIssue.EXTREME_PRICE, f"Bid price below minimum: {quote.bid_price}"))
        elif quote.bid_price > self.thresholds.max_price:
            issues.append((QualityIssue.EXTREME_PRICE, f"Bid price above maximum: {quote.bid_price}"))
        
        # Check ask price
        if quote.ask_price < 0:
            issues.append((QualityIssue.NEGATIVE_PRICE, f"Negative ask price: {quote.ask_price}"))
        elif quote.ask_price == 0:
            issues.append((QualityIssue.ZERO_PRICE, f"Zero ask price"))
        elif quote.ask_price < self.thresholds.min_price:
            issues.append((QualityIssue.EXTREME_PRICE, f"Ask price below minimum: {quote.ask_price}"))
        elif quote.ask_price > self.thresholds.max_price:
            issues.append((QualityIssue.EXTREME_PRICE, f"Ask price above maximum: {quote.ask_price}"))
        
        # Check crossed market
        if quote.bid_price > quote.ask_price:
            issues.append((QualityIssue.CROSSED_MARKET, f"Crossed market: bid {quote.bid_price} > ask {quote.ask_price}"))
        
        # Check spread
        spread_bps = quote.spread_bps
        if spread_bps > self.thresholds.max_spread_bps:
            warnings.append((QualityIssue.INVALID_SPREAD, f"Large spread: {spread_bps:.2f} bps"))
        
        # Check bid size
        if quote.bid_size < 0:
            issues.append((QualityIssue.NEGATIVE_VOLUME, f"Negative bid size: {quote.bid_size}"))
        elif quote.bid_size == 0:
            warnings.append((QualityIssue.ZERO_VOLUME, f"Zero bid size"))
        elif quote.bid_size > self.thresholds.max_volume:
            warnings.append((QualityIssue.EXTREME_VOLUME, f"Large bid size: {quote.bid_size}"))
        
        # Check ask size
        if quote.ask_size < 0:
            issues.append((QualityIssue.NEGATIVE_VOLUME, f"Negative ask size: {quote.ask_size}"))
        elif quote.ask_size == 0:
            warnings.append((QualityIssue.ZERO_VOLUME, f"Zero ask size"))
        elif quote.ask_size > self.thresholds.max_volume:
            warnings.append((QualityIssue.EXTREME_VOLUME, f"Large ask size: {quote.ask_size}"))
        
        # Statistical validation against history
        self._update_price_history(symbol, quote.mid_price)
        self._update_volume_history(symbol, quote.bid_size + quote.ask_size)
        
        stat_issues, stat_warnings = self._validate_statistical(symbol, quote.mid_price)
        issues.extend(stat_issues)
        warnings.extend(stat_warnings)
        
        return issues, warnings
    
    def _validate_trade(self, trade: Trade, symbol: str) -> List[Tuple]:
        """Validate trade data."""
        issues = []
        warnings = []
        
        # Check price
        if trade.price < 0:
            issues.append((QualityIssue.NEGATIVE_PRICE, f"Negative trade price: {trade.price}"))
        elif trade.price == 0:
            issues.append((QualityIssue.ZERO_PRICE, f"Zero trade price"))
        elif trade.price < self.thresholds.min_price:
            issues.append((QualityIssue.EXTREME_PRICE, f"Trade price below minimum: {trade.price}"))
        elif trade.price > self.thresholds.max_price:
            issues.append((QualityIssue.EXTREME_PRICE, f"Trade price above maximum: {trade.price}"))
        
        # Check quantity
        if trade.quantity < 0:
            issues.append((QualityIssue.NEGATIVE_VOLUME, f"Negative trade quantity: {trade.quantity}"))
        elif trade.quantity == 0:
            issues.append((QualityIssue.ZERO_VOLUME, f"Zero trade quantity"))
        elif trade.quantity > self.thresholds.max_volume:
            warnings.append((QualityIssue.EXTREME_VOLUME, f"Large trade quantity: {trade.quantity}"))
        
        # Statistical validation
        self._update_price_history(symbol, trade.price)
        self._update_volume_history(symbol, trade.quantity)
        
        stat_issues, stat_warnings = self._validate_statistical(symbol, trade.price)
        issues.extend(stat_issues)
        warnings.extend(stat_warnings)
        
        return issues, warnings
    
    def _validate_timestamp(self, tick: TickData) -> List[Tuple]:
        """Validate timestamp."""
        issues = []
        warnings = []
        
        # Check staleness
        if tick.symbol in self.last_timestamps:
            time_diff = tick.timestamp - self.last_timestamps[tick.symbol]
            if abs(time_diff.total_seconds()) > self.thresholds.max_staleness_seconds:
                warnings.append((QualityIssue.STALE_DATA, f"Stale data: {time_diff.total_seconds():.0f}s gap"))
        
        # Check for out-of-order timestamps
        if tick.symbol in self.last_timestamps:
            if tick.timestamp < self.last_timestamps[tick.symbol]:
                warnings.append((QualityIssue.OUT_OF_ORDER, f"Out-of-order timestamp"))
        
        self.last_timestamps[tick.symbol] = tick.timestamp
        
        return issues, warnings
    
    def _validate_sequence(self, tick: TickData) -> List[Tuple]:
        """Validate sequence number."""
        issues = []
        warnings = []
        
        # Check for sequence gaps
        if tick.symbol in self.last_sequence_numbers:
            gap = tick.sequence_number - self.last_sequence_numbers[tick.symbol]
            if gap > self.thresholds.max_sequence_gap:
                warnings.append((QualityIssue.SEQUENCE_GAP, f"Large sequence gap: {gap}"))
            elif gap < 0:
                warnings.append((QualityIssue.OUT_OF_ORDER, f"Decreasing sequence number"))
        
        self.last_sequence_numbers[tick.symbol] = tick.sequence_number
        
        return issues, warnings
    
    def _validate_statistical(self, symbol: str, price: float) -> List[Tuple]:
        """Validate against statistical history."""
        issues = []
        warnings = []
        
        if symbol not in self.price_history or len(self.price_history[symbol]) < 10:
            return issues, warnings
        
        prices = self.price_history[symbol]
        last_price = prices[-1]
        
        # Check for extreme price change
        price_change_pct = abs((price - last_price) / last_price) * 100 if last_price > 0 else 0
        if price_change_pct > self.thresholds.max_price_change_pct:
            warnings.append((QualityIssue.EXTREME_PRICE, f"Large price change: {price_change_pct:.2f}%"))
        
        # Check for statistical outliers
        if len(prices) >= 30:
            mean_price = statistics.mean(prices)
            std_price = statistics.stdev(prices) if len(prices) > 1 else 0
            
            if std_price > 0:
                z_score = abs((price - mean_price) / std_price)
                if z_score > 5:  # 5 sigma
                    warnings.append((QualityIssue.EXTREME_PRICE, f"Statistical outlier: {z_score:.2f} sigma"))
        
        return issues, warnings
    
    def _update_price_history(self, symbol: str, price: float) -> None:
        """Update price history for statistical validation."""
        if symbol not in self.price_history:
            self.price_history[symbol] = []
        
        self.price_history[symbol].append(price)
        
        # Keep only last 1000 prices
        if len(self.price_history[symbol]) > 1000:
            self.price_history[symbol] = self.price_history[symbol][-1000:]
    
    def _update_volume_history(self, symbol: str, volume: float) -> None:
        """Update volume history for statistical validation."""
        if symbol not in self.volume_history:
            self.volume_history[symbol] = []
        
        self.volume_history[symbol].append(volume)
        
        # Keep only last 1000 volumes
        if len(self.volume_history[symbol]) > 1000:
            self.volume_history[symbol] = self.volume_history[symbol][-1000:]
    
    def _calculate_quality_score(self, 
                                issues: List[Tuple],
                                warnings: List[Tuple]) -> float:
        """
        Calculate overall quality score.
        
        Args:
            issues: List of quality issues
            warnings: List of quality warnings
            
        Returns:
            Quality score (0-1)
        """
        # Base score
        score = 1.0
        
        # Deduct for issues
        score -= len(issues) * 0.5
        
        # Deduct for warnings
        score -= len(warnings) * 0.1
        
        # Ensure score is in [0, 1]
        return max(0.0, min(1.0, score))
    
    def validate_batch(self, ticks: List[TickData]) -> Dict[str, QualityValidationResult]:
        """
        Validate a batch of ticks.
        
        Args:
            ticks: List of ticks to validate
            
        Returns:
            Dictionary mapping tick_id to validation result
        """
        results = {}
        
        for tick in ticks:
            result = self.validate_tick(tick)
            results[tick.tick_id] = result
        
        return results
    
    def get_quality_summary(self) -> Dict:
        """Get summary of quality validation."""
        total_symbols = len(self.price_history)
        
        if total_symbols == 0:
            return {
                "total_symbols": 0,
                "total_price_points": 0,
                "total_volume_points": 0,
                "avg_price_history_length": 0,
                "avg_volume_history_length": 0
            }
        
        total_price_points = sum(len(prices) for prices in self.price_history.values())
        total_volume_points = sum(len(volumes) for volumes in self.volume_history.values())
        
        return {
            "total_symbols": total_symbols,
            "total_price_points": total_price_points,
            "total_volume_points": total_volume_points,
            "avg_price_history_length": total_price_points / total_symbols,
            "avg_volume_history_length": total_volume_points / total_symbols
        }


__all__ = [
    "QualityIssue",
    "QualityThresholds",
    "QualityValidationResult",
    "DataQualityValidator"
]