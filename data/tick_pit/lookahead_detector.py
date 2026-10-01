"""
Look-ahead bias detection for PIT correctness.

This implements institutional-grade lookahead bias prevention:
- Detection of future information leakage
- Temporal boundary validation
- Data snooping detection
- Reproducibility guarantees
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple
import hashlib

from .tick_data import TickData, TickType
from .timestamps import DataTimestamps, TimestampType


class BiasType(Enum):
    """Lookahead bias type enumeration."""
    FUTURE_DATA_LEAKAGE = "FUTURE_DATA_LEAKAGE"
    TEMPORAL_VIOLATION = "TEMPORAL_VIOLATION"
    DATA_SNOOPING = "DATA_SNOOPING"
    REVISION_BIAS = "REVISION_BIAS"
    CALENDAR_BIAS = "CALENDAR_BIAS"


@dataclass
class BiasReport:
    """
    Report of lookahead bias detection.
    """
    has_bias: bool
    bias_type: Optional[BiasType] = None
    bias_description: str = ""
    affected_ticks: List[str] = field(default_factory=list)
    severity: str = "LOW"  # LOW, MEDIUM, HIGH, CRITICAL
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    recommendations: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "has_bias": self.has_bias,
            "bias_type": self.bias_type.value if self.bias_type else None,
            "bias_description": self.bias_description,
            "affected_ticks": self.affected_ticks,
            "severity": self.severity,
            "timestamp": self.timestamp.isoformat(),
            "recommendations": self.recommendations
        }


class LookaheadBiasDetector:
    """
    Detects and prevents lookahead bias in data processing.
    
    Features:
    - Temporal boundary validation
    - Future data leakage detection
    - Data snooping detection
    - Revision bias detection
    - Calendar bias detection
    """
    
    def __init__(self, strict_mode: bool = True):
        """
        Initialize lookahead bias detector.
        
        Args:
            strict_mode: If True, any bias is critical; if False, bias is downgraded
        """
        self.strict_mode = strict_mode
        
        # Track data timestamps
        self.tick_timestamps: Dict[str, DataTimestamps] = {}
        self.decision_timestamps: Dict[str, datetime] = {}
        
        # Track data revisions
        self.revision_history: Dict[str, List[datetime]] = {}
        
        # Track data access patterns
        self.access_patterns: Dict[str, List[datetime]] = {}
    
    def validate_temporal_boundary(self,
                                  tick: TickData,
                                  timestamps: DataTimestamps,
                                  decision_time: Optional[datetime] = None) -> BiasReport:
        """
        Validate temporal boundary for tick data.
        
        Args:
            tick: Tick data to validate
            timestamps: Complete timestamp set
            decision_time: Decision timestamp (if known)
            
        Returns:
            Bias report
        """
        issues = []
        affected_ticks = []
        
        # Critical rule: usable_information <= decision_timestamp
        if decision_time is not None:
            if timestamps.available_timestamp > decision_time:
                issues.append((BiasType.TEMPORAL_VIOLATION, 
                            f"Data available {timestamps.available_timestamp} after decision {decision_time}"))
                affected_ticks.append(tick.tick_id)
        
        # Check for future data leakage
        now = datetime.now(timezone.utc)
        if timestamps.event_time > now:
            issues.append((BiasType.FUTURE_DATA_LEAKAGE,
                        f"Event time {timestamps.event_time} is in the future"))
            affected_ticks.append(tick.tick_id)
        
        # Check for data snooping (unusual access patterns)
        if tick.symbol in self.access_patterns:
            recent_access = [t for t in self.access_patterns[tick.symbol] 
                           if now - t < timedelta(minutes=5)]
            if len(recent_access) > 100:  # More than 100 accesses in 5 minutes
                issues.append((BiasType.DATA_SNOOPING,
                            f"Unusual access pattern: {len(recent_access)} accesses in 5 minutes"))
        
        # Update access tracking
        if tick.symbol not in self.access_patterns:
            self.access_patterns[tick.symbol] = []
        self.access_patterns[tick.symbol].append(now)
        
        # Store timestamps
        self.tick_timestamps[tick.tick_id] = timestamps
        if decision_time:
            self.decision_timestamps[tick.tick_id] = decision_time
        
        # Generate report
        if issues:
            bias_type, description = issues[0]
            severity = "CRITICAL" if self.strict_mode else "HIGH"
            
            recommendations = [
                "Ensure data available_timestamp <= decision_timestamp",
                "Use PIT queries with proper time filtering",
                "Validate clock synchronization across data sources"
            ]
            
            return BiasReport(
                has_bias=True,
                bias_type=bias_type,
                bias_description=description,
                affected_ticks=affected_ticks,
                severity=severity,
                recommendations=recommendations
            )
        
        return BiasReport(has_bias=False)
    
    def detect_revision_bias(self,
                            tick_id: str,
                            new_timestamps: DataTimestamps) -> BiasReport:
        """
        Detect bias from data revisions.
        
        Args:
            tick_id: Tick identifier
            new_timestamps: New timestamp set
            
        Returns:
            Bias report
        """
        if tick_id not in self.tick_timestamps:
            # No previous data, cannot detect revision bias
            return BiasReport(has_bias=False)
        
        old_timestamps = self.tick_timestamps[tick_id]
        
        # Check if revision timestamp changed
        if (old_timestamps.revision_timestamp != new_timestamps.revision_timestamp and
            new_timestamps.revision_timestamp is not None):
            
            # Track revision
            if tick_id not in self.revision_history:
                self.revision_history[tick_id] = []
            self.revision_history[tick_id].append(new_timestamps.revision_timestamp)
            
            # Check if revision happened after decision
            if tick_id in self.decision_timestamps:
                decision_time = self.decision_timestamps[tick_id]
                if new_timestamps.revision_timestamp > decision_time:
                    return BiasReport(
                        has_bias=True,
                        bias_type=BiasType.REVISION_BIAS,
                        bias_description=f"Data revised at {new_timestamps.revision_timestamp} after decision at {decision_time}",
                        affected_ticks=[tick_id],
                        severity="HIGH",
                        recommendations=[
                            "Use original data for decision-making",
                            "Track data revisions separately",
                            "Implement revision-aware PIT queries"
                        ]
                    )
        
        return BiasReport(has_bias=False)
    
    def detect_calendar_bias(self,
                             symbol: str,
                             event_time: datetime,
                             trading_calendar_hours: Tuple[datetime, datetime]) -> BiasReport:
        """
        Detect calendar bias (using non-trading hours data).
        
        Args:
            symbol: Symbol to check
            event_time: Event timestamp
            trading_calendar_hours: (market_open, market_close)
            
        Returns:
            Bias report
        """
        market_open, market_close = trading_calendar_hours
        
        # Check if event time is outside trading hours
        if event_time < market_open or event_time > market_close:
            return BiasReport(
                has_bias=True,
                bias_type=BiasType.CALENDAR_BIAS,
                bias_description=f"Event time {event_time} outside trading hours {market_open}-{market_close}",
                affected_ticks=[symbol],
                severity="MEDIUM",
                recommendations=[
                    "Filter data to trading hours only",
                    "Use pre-market and after-market data separately",
                    "Document off-hours data usage"
                ]
            )
        
        return BiasReport(has_bias=False)
    
    def validate_reproducibility(self,
                               experiment_id: str,
                               tick_ids: List[str],
                               manifest: Dict) -> BiasReport:
        """
        Validate experiment reproducibility against manifest.
        
        Args:
            experiment_id: Experiment identifier
            tick_ids: List of tick IDs used
            manifest: Experiment manifest with expected data
            
        Returns:
            Bias report
        """
        issues = []
        
        # Check if all expected ticks are present
        expected_ticks = manifest.get("expected_tick_ids", set())
        actual_ticks = set(tick_ids)
        
        missing_ticks = expected_ticks - actual_ticks
        extra_ticks = actual_ticks - expected_ticks
        
        if missing_ticks:
            issues.append((BiasType.DATA_SNOOPING,
                        f"Missing expected ticks: {len(missing_ticks)}"))
        
        if extra_ticks:
            issues.append((BiasType.DATA_SNOOPING,
                        f"Extra ticks not in manifest: {len(extra_ticks)}"))
        
        # Check timestamp consistency
        expected_timestamp_hash = manifest.get("timestamp_hash")
        if expected_timestamp_hash:
            actual_timestamp_hash = self._compute_timestamp_hash(tick_ids)
            if actual_timestamp_hash != expected_timestamp_hash:
                issues.append((BiasType.TEMPORAL_VIOLATION,
                            "Timestamp hash mismatch with manifest"))
        
        if issues:
            return BiasReport(
                has_bias=True,
                bias_type=issues[0][0],
                bias_description=issues[0][1],
                affected_ticks=list(missing_ticks) + list(extra_ticks),
                severity="CRITICAL",
                recommendations=[
                    "Ensure exact data reproduction",
                    "Use immutable data snapshots",
                    "Verify PIT consistency"
                ]
            )
        
        return BiasReport(has_bias=False)
    
    def _compute_timestamp_hash(self, tick_ids: List[str]) -> str:
        """Compute hash of timestamps for reproducibility check."""
        timestamp_strs = []
        for tick_id in tick_ids:
            if tick_id in self.tick_timestamps:
                ts = self.tick_timestamps[tick_id]
                timestamp_strs.append(ts.compute_hash())
        
        combined = "|".join(sorted(timestamp_strs))
        return hashlib.sha256(combined.encode()).hexdigest()[:16]
    
    def generate_pit_manifest(self, 
                             symbol: str,
                             as_of: datetime,
                             tick_ids: List[str]) -> Dict:
        """
        Generate PIT manifest for reproducibility.
        
        Args:
            symbol: Symbol for manifest
            as_of: As-of timestamp
            tick_ids: List of tick IDs included
            
        Returns:
            Manifest dictionary
        """
        return {
            "symbol": symbol,
            "as_of": as_of.isoformat(),
            "tick_ids": tick_ids,
            "timestamp_hash": self._compute_timestamp_hash(tick_ids),
            "num_ticks": len(tick_ids),
            "decision_timestamp": datetime.now(timezone.utc).isoformat(),
            "data_source_fingerprint": self._compute_data_fingerprint(tick_ids)
        }
    
    def _compute_data_fingerprint(self, tick_ids: List[str]) -> str:
        """Compute data fingerprint for source tracking."""
        combined = "|".join(sorted(tick_ids))
        return hashlib.sha256(combined.encode()).hexdigest()[:16]
    
    def clear_tracking(self) -> None:
        """Clear all tracking data."""
        self.tick_timestamps.clear()
        self.decision_timestamps.clear()
        self.revision_history.clear()
        self.access_patterns.clear()


__all__ = [
    "BiasType",
    "BiasReport",
    "LookaheadBiasDetector"
]