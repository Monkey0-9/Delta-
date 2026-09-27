"""
Realistic latency modeling for institutional trading systems.

This models the complete latency chain:
- Network latency (exchange ↔ gateway)
- Processing latency (matching engine)
- Queue delay (order queue)
- Market data latency
- Total round-trip latency
"""
from __future__ import annotations

import random
import numpy as np
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Tuple
import time


class LatencyDistribution(Enum):
    """Latency distribution types."""
    FIXED = "FIXED"
    NORMAL = "NORMAL"
    EXPONENTIAL = "EXPONENTIAL"
    LOG_NORMAL = "LOG_NORMAL"
    PARETO = "PARETO"


__all__ = [
    "LatencyDistribution",
    "LatencyMeasurement",
    "LatencyModel"
]


@dataclass
class LatencyMeasurement:
    """
    Single latency measurement with metadata.
    """
    timestamp: datetime
    latency_ms: float
    component: str  # NETWORK, PROCESSING, QUEUE, TOTAL
    exchange: str
    symbol: str


class LatencyModel:
    """
    Realistic latency model for institutional trading.
    
    Models different latency distributions and components:
    - Network latency (exchange ↔ gateway)
    - Processing latency (matching engine)
    - Queue delay (order queue)
    - Market data latency
    """
    
    def __init__(self,
                 network_latency_ms: float = 0.5,
                 processing_latency_ms: float = 0.1,
                 queue_latency_ms: float = 0.2,
                 distribution: LatencyDistribution = LatencyDistribution.LOG_NORMAL,
                 jitter_factor: float = 0.3):
        """
        Initialize latency model.
        
        Args:
            network_latency_ms: Base network latency
            processing_latency_ms: Base processing latency
            queue_latency_ms: Base queue latency
            distribution: Latency distribution type
            jitter_factor: Amount of random variation (0-1)
        """
        self.network_latency_ms = network_latency_ms
        self.processing_latency_ms = processing_latency_ms
        self.queue_latency_ms = queue_latency_ms
        self.distribution = distribution
        self.jitter_factor = jitter_factor
        
        # Latency history for percentile calculations
        self.latency_history: list[LatencyMeasurement] = []
        
        # Performance targets
        self.p50_target_ms = 1.0
        self.p95_target_ms = 2.0
        self.p99_target_ms = 5.0
        self.p99_9_target_ms = 10.0
    
    def sample_latency(self, 
                     component: str = "TOTAL",
                     exchange: str = "SIM",
                     symbol: str = "DEFAULT") -> float:
        """
        Sample latency from configured distribution.
        """
        base_latency = self._get_base_latency(component)
        
        if self.distribution == LatencyDistribution.FIXED:
            return base_latency
        
        elif self.distribution == LatencyDistribution.NORMAL:
            # Normal distribution with mean = base, std = jitter * base
            jitter = base_latency * self.jitter_factor
            return max(0.1, random.gauss(base_latency, jitter))
        
        elif self.distribution == LatencyDistribution.EXPONENTIAL:
            # Exponential distribution with mean = base
            return random.expovariate(1.0 / base_latency)
        
        elif self.distribution == LatencyDistribution.LOG_NORMAL:
            # Log-normal distribution for realistic latency tails
            mu = np.log(base_latency)
            sigma = self.jitter_factor
            return max(0.1, random.lognormvariate(mu, sigma))
        
        elif self.distribution == LatencyDistribution.PARETO:
            # Pareto distribution for heavy tails
            alpha = 2.0  # Shape parameter
            xm = base_latency * 0.5  # Scale parameter
            return (xm * (1.0 + random.random()) ** (-1.0 / alpha))
        
        else:
            return base_latency
    
    def _get_base_latency(self, component: str) -> float:
        """Get base latency for component."""
        if component == "NETWORK":
            return self.network_latency_ms
        elif component == "PROCESSING":
            return self.processing_latency_ms
        elif component == "QUEUE":
            return self.queue_latency_ms
        else:  # TOTAL
            return self.network_latency_ms + self.processing_latency_ms + self.queue_latency_ms
    
    def measure_latency(self,
                      component: str = "TOTAL",
                      exchange: str = "SIM",
                      symbol: str = "DEFAULT") -> LatencyMeasurement:
        """
        Measure and record latency.
        """
        start_time = time.perf_counter()
        
        # Simulate work
        latency = self.sample_latency(component, exchange, symbol)
        
        end_time = time.perf_counter()
        actual_latency = (end_time - start_time) * 1000  # Convert to ms
        
        measurement = LatencyMeasurement(
            timestamp=datetime.now(timezone.utc),
            latency_ms=actual_latency,
            component=component,
            exchange=exchange,
            symbol=symbol
        )
        
        self.latency_history.append(measurement)
        
        # Keep only last 10,000 measurements
        if len(self.latency_history) > 10000:
            self.latency_history = self.latency_history[-10000:]
        
        return measurement
    
    def get_percentiles(self, component: str = "TOTAL") -> dict:
        """
        Get latency percentiles for component.
        """
        measurements = [
            m.latency_ms for m in self.latency_history 
            if m.component == component
        ]
        
        if not measurements:
            return {
                "p50": 0.0,
                "p95": 0.0,
                "p99": 0.0,
                "p99_9": 0.0,
                "mean": 0.0,
                "min": 0.0,
                "max": 0.0
            }
        
        measurements_sorted = sorted(measurements)
        
        return {
            "p50": measurements_sorted[int(len(measurements_sorted) * 0.5)],
            "p95": measurements_sorted[int(len(measurements_sorted) * 0.95)],
            "p99": measurements_sorted[int(len(measurements_sorted) * 0.99)],
            "p99_9": measurements_sorted[int(len(measurements_sorted) * 0.999)],
            "mean": np.mean(measurements),
            "min": measurements_sorted[0],
            "max": measurements_sorted[-1]
        }
    
    def check_sla_compliance(self, component: str = "TOTAL") -> dict:
        """
        Check if latency meets SLA targets.
        """
        percentiles = self.get_percentiles(component)
        
        return {
            "p50_compliant": percentiles["p50"] <= self.p50_target_ms,
            "p95_compliant": percentiles["p95"] <= self.p95_target_ms,
            "p99_compliant": percentiles["p99"] <= self.p99_target_ms,
            "p99_9_compliant": percentiles["p99_9"] <= self.p99_9_target_ms,
            "overall_compliant": all([
                percentiles["p50"] <= self.p50_target_ms,
                percentiles["p95"] <= self.p95_target_ms,
                percentiles["p99"] <= self.p99_target_ms,
                percentiles["p99_9"] <= self.p99_9_target_ms
            ])
        }
    
    def set_targets(self,
                   p50_ms: float,
                   p95_ms: float,
                   p99_ms: float,
                   p99_9_ms: float) -> None:
        """Set latency SLA targets."""
        self.p50_target_ms = p50_ms
        self.p95_target_ms = p95_ms
        self.p99_target_ms = p99_ms
        self.p99_9_target_ms = p99_9_ms
    
    def get_tail_latency_ratio(self, component: str = "TOTAL") -> float:
        """
        Calculate tail latency ratio (p99 / p50).
        
        Higher ratios indicate more tail latency.
        """
        percentiles = self.get_percentiles(component)
        
        if percentiles["p50"] == 0:
            return 0.0
        
        return percentiles["p99"] / percentiles["p50"]
    
    def simulate_end_to_end_latency(self,
                                    order_size: float,
                                    market_conditions: str = "NORMAL") -> float:
        """
        Simulate complete end-to-end latency for an order.
        
        Includes:
        - Order submission latency
        - Matching engine processing
        - Fill generation
        - Fill acknowledgment
        """
        # Base latency varies by market conditions
        condition_multiplier = {
            "NORMAL": 1.0,
            "VOLATILE": 1.5,
            "STRESSED": 2.0,
            "CRASH": 3.0
        }.get(market_conditions, 1.0)
        
        # Order submission
        submit_latency = self.sample_latency("NETWORK") * condition_multiplier
        
        # Queue delay (increases with order size)
        queue_delay = self.sample_latency("QUEUE") * (1 + order_size / 10000) * condition_multiplier
        
        # Processing
        processing_latency = self.sample_latency("PROCESSING") * condition_multiplier
        
        # Fill generation
        fill_latency = self.sample_latency("PROCESSING") * condition_multiplier
        
        # Fill acknowledgment
        ack_latency = self.sample_latency("NETWORK") * condition_multiplier
        
        total_latency = submit_latency + queue_delay + processing_latency + fill_latency + ack_latency
        
        return total_latency
    
    def clear_history(self) -> None:
        """Clear latency history."""
        self.latency_history.clear()
    
    def get_statistics_summary(self) -> dict:
        """Get comprehensive latency statistics summary."""
        total_measurements = len(self.latency_history)
        
        if total_measurements == 0:
            return {
                "total_measurements": 0,
                "components": {}
            }
        
        components = set(m.component for m in self.latency_history)
        
        component_stats = {}
        for component in components:
            component_stats[component] = {
                "percentiles": self.get_percentiles(component),
                "sla_compliance": self.check_sla_compliance(component),
                "tail_ratio": self.get_tail_latency_ratio(component),
                "measurement_count": len([m for m in self.latency_history if m.component == component])
            }
        
        return {
            "total_measurements": total_measurements,
            "components": component_stats,
            "distribution": self.distribution.value,
            "jitter_factor": self.jitter_factor
        }