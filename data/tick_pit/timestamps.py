"""
Multi-timestamp management for point-in-time correctness.

This implements institutional-grade timestamp management:
- Multiple timestamp types (event_time, available_time, published_time, etc.)
- Timestamp validation and consistency checking
- Timezone handling
- Sequence number management
- Clock synchronization detection
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Dict, List, Optional, Set
import hashlib


class TimestampType(Enum):
    """Timestamp type enumeration."""
    EVENT_TIME = "event_time"  # When the event actually occurred
    SOURCE_TIMESTAMP = "source_timestamp"  # Timestamp from data source
    PUBLICATION_TIMESTAMP = "publication_timestamp"  # When data was published
    AVAILABLE_TIMESTAMP = "available_timestamp"  # When data became available
    INGESTION_TIMESTAMP = "ingestion_timestamp"  # When data was ingested
    REVISION_TIMESTAMP = "revision_timestamp"  # Last revision time
    DECISION_TIMESTAMP = "decision_timestamp"  # When decision was made
    PROCESSING_TIMESTAMP = "processing_timestamp"  # When processing occurred


@dataclass(frozen=True, slots=True)
class DataTimestamps:
    """
    Complete timestamp set for PIT correctness.
    
    Critical Rule: usable_information <= decision_timestamp
    """
    event_time: datetime
    source_timestamp: datetime
    publication_timestamp: datetime
    available_timestamp: datetime
    ingestion_timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    revision_timestamp: Optional[datetime] = None
    decision_timestamp: Optional[datetime] = None
    processing_timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "event_time": self.event_time.isoformat(),
            "source_timestamp": self.source_timestamp.isoformat(),
            "publication_timestamp": self.publication_timestamp.isoformat(),
            "available_timestamp": self.available_timestamp.isoformat(),
            "ingestion_timestamp": self.ingestion_timestamp.isoformat(),
            "revision_timestamp": self.revision_timestamp.isoformat() if self.revision_timestamp else None,
            "decision_timestamp": self.decision_timestamp.isoformat() if self.decision_timestamp else None,
            "processing_timestamp": self.processing_timestamp.isoformat()
        }
    
    def get_delay(self, from_type: TimestampType, to_type: TimestampType) -> timedelta:
        """
        Calculate delay between two timestamp types.
        
        Args:
            from_type: Starting timestamp type
            to_type: Ending timestamp type
            
        Returns:
            Time difference
        """
        from_time = self._get_timestamp(from_type)
        to_time = self._get_timestamp(to_type)
        
        if from_time is None or to_time is None:
            return timedelta(0)
        
        return to_time - from_time
    
    def _get_timestamp(self, timestamp_type: TimestampType) -> Optional[datetime]:
        """Get timestamp by type."""
        mapping = {
            TimestampType.EVENT_TIME: self.event_time,
            TimestampType.SOURCE_TIMESTAMP: self.source_timestamp,
            TimestampType.PUBLICATION_TIMESTAMP: self.publication_timestamp,
            TimestampType.AVAILABLE_TIMESTAMP: self.available_timestamp,
            TimestampType.INGESTION_TIMESTAMP: self.ingestion_timestamp,
            TimestampType.REVISION_TIMESTAMP: self.revision_timestamp,
            TimestampType.DECISION_TIMESTAMP: self.decision_timestamp,
            TimestampType.PROCESSING_TIMESTAMP: self.processing_timestamp
        }
        return mapping.get(timestamp_type)
    
    def validate_consistency(self) -> List[str]:
        """
        Validate timestamp consistency.
        
        Returns:
            List of validation errors (empty if valid)
        """
        errors = []
        
        # Event time should be earliest
        if self.event_time > self.source_timestamp:
            errors.append("event_time > source_timestamp")
        
        if self.event_time > self.publication_timestamp:
            errors.append("event_time > publication_timestamp")
        
        # Publication should be before availability
        if self.publication_timestamp > self.available_timestamp:
            errors.append("publication_timestamp > available_timestamp")
        
        # Ingestion should be after availability
        if self.available_timestamp > self.ingestion_timestamp:
            errors.append("available_timestamp > ingestion_timestamp")
        
        # Decision should be after availability
        if self.decision_timestamp and self.available_timestamp > self.decision_timestamp:
            errors.append("available_timestamp > decision_timestamp")
        
        return errors
    
    def compute_hash(self) -> str:
        """Compute hash of timestamps for versioning."""
        timestamp_str = "|".join([
            self.event_time.isoformat(),
            self.source_timestamp.isoformat(),
            self.publication_timestamp.isoformat(),
            self.available_timestamp.isoformat(),
            self.ingestion_timestamp.isoformat(),
            self.revision_timestamp.isoformat() if self.revision_timestamp else "",
            self.decision_timestamp.isoformat() if self.decision_timestamp else ""
        ])
        
        return hashlib.sha256(timestamp_str.encode()).hexdigest()[:16]


class TimestampManager:
    """
    Manages timestamps for PIT correctness.
    
    Features:
    - Timestamp validation
    - Clock skew detection
    - Timezone normalization
    - Sequence number management
    """
    
    def __init__(self, max_clock_skew_ms: float = 1000.0):
        """
        Initialize timestamp manager.
        
        Args:
            max_clock_skew_ms: Maximum allowed clock skew in milliseconds
        """
        self.max_clock_skew_ms = max_clock_skew_ms
        self.clock_offsets: Dict[str, timedelta] = {}  # Source -> clock offset
        self.sequence_numbers: Dict[str, int] = {}  # Source -> sequence number
    
    def normalize_timestamp(self, 
                          timestamp: datetime,
                          source: str = "DEFAULT",
                          target_timezone: timezone = timezone.utc) -> datetime:
        """
        Normalize timestamp to target timezone.
        
        Args:
            timestamp: Input timestamp
            source: Data source identifier
            target_timezone: Target timezone
            
        Returns:
            Normalized timestamp
        """
        # Apply clock offset if known
        if source in self.clock_offsets:
            timestamp = timestamp + self.clock_offsets[source]
        
        # Convert to target timezone
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        
        return timestamp.astimezone(target_timezone)
    
    def detect_clock_skew(self, 
                         timestamps: List[datetime],
                         expected_interval: timedelta) -> Dict:
        """
        Detect clock skew in timestamp sequence.
        
        Args:
            timestamps: List of timestamps
            expected_interval: Expected interval between timestamps
            
        Returns:
            Dictionary with skew statistics
        """
        if len(timestamps) < 2:
            return {"skew_detected": False, "max_skew_ms": 0.0}
        
        intervals = []
        for i in range(1, len(timestamps)):
            interval = timestamps[i] - timestamps[i-1]
            intervals.append(interval)
        
        # Calculate statistics
        avg_interval = sum(intervals, timedelta()) / len(intervals)
        max_deviation = max(abs(interval - avg_interval) for interval in intervals)
        
        skew_detected = max_deviation > timedelta(milliseconds=self.max_clock_skew_ms)
        
        return {
            "skew_detected": skew_detected,
            "max_skew_ms": max_deviation.total_seconds() * 1000,
            "avg_interval_ms": avg_interval.total_seconds() * 1000,
            "expected_interval_ms": expected_interval.total_seconds() * 1000
        }
    
    def register_clock_offset(self, source: str, offset: timedelta) -> None:
        """
        Register clock offset for a data source.
        
        Args:
            source: Data source identifier
            offset: Clock offset to apply
        """
        self.clock_offsets[source] = offset
    
    def get_next_sequence_number(self, source: str) -> int:
        """
        Get next sequence number for source.
        
        Args:
            source: Data source identifier
            
        Returns:
            Next sequence number
        """
        if source not in self.sequence_numbers:
            self.sequence_numbers[source] = 0
        
        self.sequence_numbers[source] += 1
        return self.sequence_numbers[source]
    
    def create_timestamps(self,
                        event_time: datetime,
                        source: str = "DEFAULT",
                        publication_delay_ms: float = 0.0,
                        availability_delay_ms: float = 0.0) -> DataTimestamps:
        """
        Create complete timestamp set.
        
        Args:
            event_time: Event time
            source: Data source identifier
            publication_delay_ms: Delay from event to publication
            availability_delay_ms: Delay from publication to availability
            
        Returns:
            Complete DataTimestamps
        """
        # Normalize event time
        normalized_event = self.normalize_timestamp(event_time, source)
        
        # Calculate other timestamps
        source_timestamp = normalized_event
        publication_timestamp = normalized_event + timedelta(milliseconds=publication_delay_ms)
        available_timestamp = publication_timestamp + timedelta(milliseconds=availability_delay_ms)
        ingestion_timestamp = datetime.now(timezone.utc)
        
        # Get sequence number
        sequence_number = self.get_next_sequence_number(source)
        
        return DataTimestamps(
            event_time=normalized_event,
            source_timestamp=source_timestamp,
            publication_timestamp=publication_timestamp,
            available_timestamp=available_timestamp,
            ingestion_timestamp=ingestion_timestamp
        )
    
    def validate_timestamp_sequence(self, 
                                   timestamps: List[DataTimestamps],
                                   source: str) -> Dict:
        """
        Validate a sequence of timestamps.
        
        Args:
            timestamps: List of timestamps to validate
            source: Data source identifier
            
        Returns:
            Validation results
        """
        if not timestamps:
            return {"valid": True, "errors": []}
        
        errors = []
        
        # Check each timestamp for consistency
        for i, ts in enumerate(timestamps):
            ts_errors = ts.validate_consistency()
            for error in ts_errors:
                errors.append(f"Timestamp {i}: {error}")
        
        # Check monotonicity
        event_times = [ts.event_time for ts in timestamps]
        for i in range(1, len(event_times)):
            if event_times[i] < event_times[i-1]:
                errors.append(f"Timestamp {i}: event_time not monotonic")
        
        # Check for clock skew
        skew_result = self.detect_clock_skew(event_times, timedelta(seconds=1))
        if skew_result["skew_detected"]:
            errors.append(f"Clock skew detected: {skew_result['max_skew_ms']:.2f}ms")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "skew_result": skew_result
        }


__all__ = [
    "TimestampType",
    "DataTimestamps",
    "TimestampManager"
]