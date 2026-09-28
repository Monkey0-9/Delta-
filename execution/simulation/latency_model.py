"""
Calibrated Latency Model for Execution Simulation.

This module implements realistic latency modeling for:
- Network latency (round-trip time)
- Processing latency (order validation, risk checks)
- Exchange latency (matching engine processing)
- Queue latency (time in matching engine queue)
- Venue-specific latency profiles

Latency is modeled using statistical distributions based on
empirical measurements from real trading venues.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from enum import Enum
from typing import Optional, Dict, List, Tuple
import random
import numpy as np

from core.contracts.canonical import Instrument, Currency


class VenueType(Enum):
    """Types of trading venues with different latency characteristics."""
    EXCHANGE = "exchange"  # Major exchanges (NYSE, NASDAQ)
    ECN = "ecn"  # Electronic Communication Networks
    DARK_POOL = "dark_pool"  # Dark pools
    ATS = "ats"  # Alternative Trading Systems
    OTC = "otc"  # Over-the-counter


class LatencyComponent(Enum):
    """Components of total latency."""
    NETWORK_OUTBOUND = "network_outbound"  # Client to exchange
    EXCHANGE_PROCESSING = "exchange_processing"  # Matching engine
    QUEUE_DELAY = "queue_delay"  # Time in exchange queue
    NETWORK_INBOUND = "network_inbound"  # Exchange to client
    RISK_CHECK = "risk_check"  # Pre-trade risk validation
    ORDER_VALIDATION = "order_validation"  # Order validation logic
    TOTAL = "total"  # End-to-end latency


@dataclass(frozen=True, slots=True)
class LatencyProfile:
    """
    Latency profile for a specific venue.
    
    Latency values are in microseconds (μs).
    """
    venue_name: str
    venue_type: VenueType
    
    # Network latency (μs) - log-normal distribution parameters
    network_latency_mean: float = 500.0  # 0.5ms mean
    network_latency_std: float = 200.0  # 0.2ms std
    
    # Exchange processing latency (μs)
    exchange_processing_mean: float = 100.0  # 0.1ms mean
    exchange_processing_std: float = 50.0  # 0.05ms std
    
    # Queue delay (μs) - depends on order flow
    queue_delay_mean: float = 50.0  # 0.05ms mean
    queue_delay_std: float = 30.0  # 0.03ms std
    
    # Risk check latency (μs)
    risk_check_mean: float = 200.0  # 0.2ms mean
    risk_check_std: float = 100.0  # 0.1ms std
    
    # Order validation latency (μs)
    order_validation_mean: float = 50.0  # 0.05ms mean
    order_validation_std: float = 20.0  # 0.02ms std
    
    # Reliability metrics
    success_rate: float = 0.999  # 99.9% success rate
    timeout_rate: float = 0.001  # 0.1% timeout rate


@dataclass
class LatencyMeasurement:
    """
    Individual latency measurement.
    
    Attributes:
        timestamp: When the measurement was taken
        component: Latency component measured
        latency_us: Latency in microseconds
        venue: Venue where measurement was taken
        metadata: Additional metadata
    """
    timestamp: datetime
    component: LatencyComponent
    latency_us: float
    venue: str
    metadata: Dict = field(default_factory=dict)
    
    @property
    def latency_ms(self) -> float:
        """Latency in milliseconds."""
        return self.latency_us / 1000.0
    
    @property
    def latency_seconds(self) -> float:
        """Latency in seconds."""
        return self.latency_us / 1_000_000.0


class LatencyModel:
    """
    Calibrated latency model for execution simulation.
    
    Features:
    - Venue-specific latency profiles
    - Statistical distribution sampling
    - Component-wise latency breakdown
    - Time-of-day and volatility adjustments
    - Latency percentile estimation
    """
    
    # Default venue profiles (based on typical exchange characteristics)
    DEFAULT_PROFILES: Dict[str, LatencyProfile] = {
        "NYSE": LatencyProfile(
            venue_name="NYSE",
            venue_type=VenueType.EXCHANGE,
            network_latency_mean=600.0,
            network_latency_std=250.0,
            exchange_processing_mean=150.0,
            exchange_processing_std=75.0,
            queue_delay_mean=75.0,
            queue_delay_std=40.0,
        ),
        "NASDAQ": LatencyProfile(
            venue_name="NASDAQ",
            venue_type=VenueType.EXCHANGE,
            network_latency_mean=550.0,
            network_latency_std=220.0,
            exchange_processing_mean=120.0,
            exchange_processing_std=60.0,
            queue_delay_mean=60.0,
            queue_delay_std=35.0,
        ),
        "ARCA": LatencyProfile(
            venue_name="ARCA",
            venue_type=VenueType.ECN,
            network_latency_mean=400.0,
            network_latency_std=150.0,
            exchange_processing_mean=80.0,
            exchange_processing_std=40.0,
            queue_delay_mean=40.0,
            queue_delay_std=20.0,
        ),
        "BATS": LatencyProfile(
            venue_name="BATS",
            venue_type=VenueType.ECN,
            network_latency_mean=350.0,
            network_latency_std=130.0,
            exchange_processing_mean=70.0,
            exchange_processing_std=35.0,
            queue_delay_mean=35.0,
            queue_delay_std=18.0,
        ),
    }
    
    def __init__(self, custom_profiles: Optional[Dict[str, LatencyProfile]] = None):
        """
        Initialize latency model.
        
        Args:
            custom_profiles: Custom venue profiles (overrides defaults)
        """
        self._profiles = {**self.DEFAULT_PROFILES}
        if custom_profiles:
            self._profiles.update(custom_profiles)
        
        # Latency history for analysis
        self._measurements: List[LatencyMeasurement] = []
        
        # Random seed for reproducibility
        self._seed = 42
        
    def add_profile(self, profile: LatencyProfile) -> None:
        """
        Add a custom venue profile.
        
        Args:
            profile: Latency profile to add
        """
        self._profiles[profile.venue_name] = profile
    
    def get_profile(self, venue: str) -> Optional[LatencyProfile]:
        """
        Get latency profile for a venue.
        
        Args:
            venue: Venue name
            
        Returns:
            LatencyProfile if found, None otherwise
        """
        return self._profiles.get(venue)
    
    def sample_latency(
        self,
        venue: str,
        component: LatencyComponent = LatencyComponent.TOTAL,
        volatility_adjustment: float = 1.0,
        time_of_day_adjustment: float = 1.0
    ) -> float:
        """
        Sample latency from the appropriate distribution.
        
        Args:
            venue: Venue name
            component: Latency component to sample
            volatility_adjustment: Adjustment factor for market volatility
            time_of_day_adjustment: Adjustment factor for time of day
            
        Returns:
            Latency in microseconds
        """
        profile = self.get_profile(venue)
        if profile is None:
            # Default to NASDAQ profile if venue not found
            profile = self._profiles.get("NASDAQ", self.DEFAULT_PROFILES["NASDAQ"])
        
        # Get appropriate distribution parameters
        if component == LatencyComponent.NETWORK_OUTBOUND:
            mean = profile.network_latency_mean
            std = profile.network_latency_std
        elif component == LatencyComponent.EXCHANGE_PROCESSING:
            mean = profile.exchange_processing_mean
            std = profile.exchange_processing_std
        elif component == LatencyComponent.QUEUE_DELAY:
            mean = profile.queue_delay_mean
            std = profile.queue_delay_std
        elif component == LatencyComponent.RISK_CHECK:
            mean = profile.risk_check_mean
            std = profile.risk_check_std
        elif component == LatencyComponent.ORDER_VALIDATION:
            mean = profile.order_validation_mean
            std = profile.order_validation_std
        elif component == LatencyComponent.NETWORK_INBOUND:
            mean = profile.network_latency_mean
            std = profile.network_latency_std
        elif component == LatencyComponent.TOTAL:
            # Sum of all components
            total = 0.0
            total += self.sample_latency(venue, LatencyComponent.NETWORK_OUTBOUND, 
                                       volatility_adjustment, time_of_day_adjustment)
            total += self.sample_latency(venue, LatencyComponent.EXCHANGE_PROCESSING,
                                       volatility_adjustment, time_of_day_adjustment)
            total += self.sample_latency(venue, LatencyComponent.QUEUE_DELAY,
                                       volatility_adjustment, time_of_day_adjustment)
            total += self.sample_latency(venue, LatencyComponent.NETWORK_INBOUND,
                                       volatility_adjustment, time_of_day_adjustment)
            total += self.sample_latency(venue, LatencyComponent.RISK_CHECK,
                                       volatility_adjustment, time_of_day_adjustment)
            total += self.sample_latency(venue, LatencyComponent.ORDER_VALIDATION,
                                       volatility_adjustment, time_of_day_adjustment)
            return total
        else:
            mean = 100.0
            std = 50.0
        
        # Apply adjustments
        adjusted_mean = mean * volatility_adjustment * time_of_day_adjustment
        adjusted_std = std * volatility_adjustment * time_of_day_adjustment
        
        # Sample from log-normal distribution (more realistic for latency)
        # Convert to log-space parameters
        mu = np.log(adjusted_mean**2 / np.sqrt(adjusted_std**2 + adjusted_mean**2))
        sigma = np.sqrt(np.log(1 + (adjusted_std**2 / adjusted_mean**2)))
        
        # Sample and ensure positive
        sample = np.random.lognormal(mu, sigma)
        
        # Record measurement
        measurement = LatencyMeasurement(
            timestamp=datetime.now(timezone.utc),
            component=component,
            latency_us=float(sample),
            venue=venue,
            metadata={
                "volatility_adjustment": volatility_adjustment,
                "time_of_day_adjustment": time_of_day_adjustment
            }
        )
        self._measurements.append(measurement)
        
        return float(sample)
    
    def get_percentile(
        self,
        venue: str,
        component: LatencyComponent = LatencyComponent.TOTAL,
        percentile: float = 95.0
    ) -> float:
        """
        Get latency percentile for a venue and component.
        
        Args:
            venue: Venue name
            component: Latency component
            percentile: Percentile to compute (0-100)
            
        Returns:
            Latency in microseconds at the given percentile
        """
        # Filter measurements by venue and component
        filtered = [
            m for m in self._measurements
            if m.venue == venue and m.component == component
        ]
        
        if not filtered:
            # If no measurements, estimate from profile
            profile = self.get_profile(venue)
            if profile is None:
                return 1000.0  # Default 1ms
            
            # Estimate percentile using log-normal distribution
            if component == LatencyComponent.TOTAL:
                total_mean = (
                    profile.network_latency_mean +
                    profile.exchange_processing_mean +
                    profile.queue_delay_mean +
                    profile.network_latency_mean +
                    profile.risk_check_mean +
                    profile.order_validation_mean
                )
                total_std = (
                    profile.network_latency_std +
                    profile.exchange_processing_std +
                    profile.queue_delay_std +
                    profile.network_latency_std +
                    profile.risk_check_std +
                    profile.order_validation_std
                )
            else:
                # Use component-specific parameters
                if component == LatencyComponent.NETWORK_OUTBOUND:
                    total_mean = profile.network_latency_mean
                    total_std = profile.network_latency_std
                elif component == LatencyComponent.EXCHANGE_PROCESSING:
                    total_mean = profile.exchange_processing_mean
                    total_std = profile.exchange_processing_std
                elif component == LatencyComponent.QUEUE_DELAY:
                    total_mean = profile.queue_delay_mean
                    total_std = profile.queue_delay_std
                elif component == LatencyComponent.RISK_CHECK:
                    total_mean = profile.risk_check_mean
                    total_std = profile.risk_check_std
                elif component == LatencyComponent.ORDER_VALIDATION:
                    total_mean = profile.order_validation_mean
                    total_std = profile.order_validation_std
                else:
                    total_mean = 100.0
                    total_std = 50.0
            
            mu = np.log(total_mean**2 / np.sqrt(total_std**2 + total_mean**2))
            sigma = np.sqrt(np.log(1 + (total_std**2 / total_mean**2)))
            
            return np.percentile(np.random.lognormal(mu, sigma, 10000), percentile)
        
        # Compute percentile from historical measurements
        latencies = [m.latency_us for m in filtered]
        return np.percentile(latencies, percentile)
    
    def get_latency_summary(
        self,
        venue: str,
        component: LatencyComponent = LatencyComponent.TOTAL
    ) -> Dict[str, float]:
        """
        Get latency summary statistics.
        
        Args:
            venue: Venue name
            component: Latency component
            
        Returns:
            Dictionary with summary statistics
        """
        filtered = [
            m for m in self._measurements
            if m.venue == venue and m.component == component
        ]
        
        if not filtered:
            return {
                "count": 0,
                "mean_us": 0.0,
                "std_us": 0.0,
                "min_us": 0.0,
                "max_us": 0.0,
                "p50_us": 0.0,
                "p95_us": 0.0,
                "p99_us": 0.0,
                "p99_9_us": 0.0,
            }
        
        latencies = [m.latency_us for m in filtered]
        
        return {
            "count": len(latencies),
            "mean_us": float(np.mean(latencies)),
            "std_us": float(np.std(latencies)),
            "min_us": float(np.min(latencies)),
            "max_us": float(np.max(latencies)),
            "p50_us": float(np.percentile(latencies, 50)),
            "p95_us": float(np.percentile(latencies, 95)),
            "p99_us": float(np.percentile(latencies, 99)),
            "p99_9_us": float(np.percentile(latencies, 99.9)),
        }
    
    def clear_measurements(self) -> None:
        """Clear all latency measurements."""
        self._measurements.clear()
    
    def set_seed(self, seed: int) -> None:
        """
        Set random seed for reproducibility.
        
        Args:
            seed: Random seed
        """
        self._seed = seed
        np.random.seed(seed)
        random.seed(seed)


__all__ = [
    "VenueType",
    "LatencyComponent",
    "LatencyProfile",
    "LatencyMeasurement",
    "LatencyModel",
]
