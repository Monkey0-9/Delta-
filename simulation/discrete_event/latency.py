"""Latency Model for realistic simulation timing."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import random
import numpy as np


class LatencyDistribution(StrEnum):
    """Types of latency distributions."""
    FIXED = "fixed"
    UNIFORM = "uniform"
    NORMAL = "normal"
    EXPONENTIAL = "exponential"
    LOG_NORMAL = "log_normal"


@dataclass(frozen=True, slots=True)
class LatencyConfig:
    """Configuration for latency model."""
    distribution: LatencyDistribution = LatencyDistribution.NORMAL
    mean_us: float = 100.0  # Mean latency in microseconds
    std_us: float = 20.0  # Standard deviation in microseconds
    min_us: float = 50.0  # Minimum latency
    max_us: float = 500.0  # Maximum latency


class LatencyModel:
    """
    Latency model for simulating realistic network and processing delays.
    
    Models various latency distributions for different system components:
    - Market data ingestion
    - Order submission
    - Fill confirmation
    - Risk checks
    """
    
    def __init__(self, config: LatencyConfig | None = None) -> None:
        self._config = config or LatencyConfig()
    
    def sample_latency(self) -> float:
        """Sample a latency value in microseconds."""
        dist = self._config.distribution
        
        if dist == LatencyDistribution.FIXED:
            return self._config.mean_us
        
        elif dist == LatencyDistribution.UNIFORM:
            return random.uniform(
                self._config.min_us,
                self._config.max_us
            )
        
        elif dist == LatencyDistribution.NORMAL:
            latency = random.gauss(self._config.mean_us, self._config.std_us)
            return max(self._config.min_us, min(self._config.max_us, latency))
        
        elif dist == LatencyDistribution.EXPONENTIAL:
            scale = self._config.mean_us
            latency = random.expovariate(1.0 / scale)
            return max(self._config.min_us, min(self._config.max_us, latency))
        
        elif dist == LatencyDistribution.LOG_NORMAL:
            mu = np.log(self._config.mean_us)
            sigma = self._config.std_us / self._config.mean_us
            latency = np.random.lognormal(mu, sigma)
            return max(self._config.min_us, min(self._config.max_us, latency))
        
        return self._config.mean_us
    
    def get_latency_percentiles(self, samples: int = 10000) -> dict[str, float]:
        """Get latency percentiles for analysis."""
        latencies = [self.sample_latency() for _ in range(samples)]
        
        return {
            "p50": np.percentile(latencies, 50),
            "p90": np.percentile(latencies, 90),
            "p95": np.percentile(latencies, 95),
            "p99": np.percentile(latencies, 99),
            "p99_9": np.percentile(latencies, 99.9),
            "mean": np.mean(latencies),
            "std": np.std(latencies),
        }
