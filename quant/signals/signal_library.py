"""
DELTA Comprehensive Signal Library

Top-tier quantitative signal library for financial research.
Supports momentum, mean reversion, trend, volatility, volume, 
and multi-factor signals with institutional-grade implementation.

SIGNAL CATEGORIES:
- Momentum: Price momentum across multiple timeframes
- Mean Reversion: Statistical arbitrage and reversion signals
- Trend: Trend-following and regime detection
- Volatility: Volatility-based signals and regime changes
- Volume: Volume profile and flow signals
- Factor: Cross-sectional factor models
- Regime: Market regime classification
- Sentiment: Sentiment-based signals
- Macro: Macro-economic factor signals
- Composite: Multi-signal combination strategies
"""

from __future__ import annotations

import numpy as np
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Optional, Callable, List, Dict, Tuple
import statistics


# ============================================================================
# SIGNAL METADATA
# ============================================================================

class SignalCategory(Enum):
    """Signal category classification."""
    MOMENTUM = "momentum"
    MEAN_REVERSION = "mean_reversion"
    TREND = "trend"
    VOLATILITY = "volatility"
    VOLUME = "volume"
    FACTOR = "factor"
    REGIME = "regime"
    SENTIMENT = "sentiment"
    MACRO = "macro"
    COMPOSITE = "composite"


class SignalHorizon(Enum):
    """Signal investment horizon."""
    INTRADAY = "intraday"
    SHORT = "short"  # 1-5 days
    MEDIUM = "medium"  # 1-4 weeks
    LONG = "long"  # 1-3 months
    STRATEGIC = "strategic"  # 3+ months


@dataclass(frozen=True, slots=True)
class SignalMetadata:
    """Metadata for signal reproducibility and tracking."""
    
    signal_name: str
    category: SignalCategory
    horizon: SignalHorizon
    description: str
    version: str = "1.0.0"
    author: str = "DELTA"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    parameters: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'signal_name': self.signal_name,
            'category': self.category.value,
            'horizon': self.horizon.value,
            'description': self.description,
            'version': self.version,
            'author': self.author,
            'created_at': self.created_at,
            'parameters': self.parameters,
            'tags': self.tags
        }


# ============================================================================
# SIGNAL RESULT
# ============================================================================

@dataclass(frozen=True, slots=True)
class SignalResult:
    """Result from signal computation."""
    
    signal_name: str
    values: np.ndarray
    timestamps: np.ndarray
    metadata: SignalMetadata
    
    # Signal statistics
    mean: float
    std: float
    min: float
    max: float
    sharpe: Optional[float] = None
    
    # Signal quality metrics
    hit_rate: Optional[float] = None
    information_coefficient: Optional[float] = None
    
    # Additional metadata
    computation_time_ms: Optional[float] = None
    additional_info: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'signal_name': self.signal_name,
            'values': self.values.tolist(),
            'timestamps': self.timestamps.tolist(),
            'metadata': self.metadata.to_dict(),
            'mean': self.mean,
            'std': self.std,
            'min': self.min,
            'max': self.max,
            'sharpe': self.sharpe,
            'hit_rate': self.hit_rate,
            'information_coefficient': self.information_coefficient,
            'computation_time_ms': self.computation_time_ms,
            'additional_info': self.additional_info
        }


# ============================================================================
# BASE SIGNAL CLASS
# ============================================================================

class BaseSignal:
    """
    Base class for all DELTA signals.
    
    Provides common functionality for signal computation,
    validation, and quality assessment.
    """
    
    def __init__(self, metadata: SignalMetadata):
        self.metadata = metadata
    
    def compute(self, prices: np.ndarray, timestamps: np.ndarray, **kwargs) -> SignalResult:
        """
        Compute signal values.
        
        Args:
            prices: Price series
            timestamps: Timestamp series
            **kwargs: Additional parameters
            
        Returns:
            SignalResult with computed values and metadata
        """
        raise NotImplementedError("Subclasses must implement compute")
    
    def validate_inputs(self, prices: np.ndarray, timestamps: np.ndarray) -> None:
        """Validate input data."""
        if len(prices) == 0:
            raise ValueError("Prices cannot be empty")
        if len(timestamps) == 0:
            raise ValueError("Timestamps cannot be empty")
        if len(prices) != len(timestamps):
            raise ValueError("Prices and timestamps must have same length")
        if np.any(prices <= 0):
            raise ValueError("Prices must be positive")
    
    def compute_statistics(self, values: np.ndarray) -> Dict[str, float]:
        """Compute signal statistics."""
        return {
            'mean': float(np.mean(values)),
            'std': float(np.std(values)),
            'min': float(np.min(values)),
            'max': float(np.max(values))
        }


# ============================================================================
# MOMENTUM SIGNALS
# ============================================================================

class SimpleMomentumSignal(BaseSignal):
    """
    Simple momentum signal based on price change over a lookback period.
    
    Formula: (price_t - price_t-lookback) / price_t-lookback
    """
    
    def __init__(self, lookback: int = 20):
        metadata = SignalMetadata(
            signal_name="simple_momentum",
            category=SignalCategory.MOMENTUM,
            horizon=SignalHorizon.SHORT,
            description="Simple momentum signal based on price change over lookback period",
            parameters={'lookback': lookback}
        )
        super().__init__(metadata)
        self.lookback = lookback
    
    def compute(self, prices: np.ndarray, timestamps: np.ndarray, **kwargs) -> SignalResult:
        """Compute momentum signal."""
        self.validate_inputs(prices, timestamps)
        
        if len(prices) < self.lookback + 1:
            raise ValueError(f"Need at least {self.lookback + 1} prices")
        
        # Compute momentum
        momentum = np.zeros(len(prices))
        for i in range(self.lookback, len(prices)):
            momentum[i] = (prices[i] - prices[i - self.lookback]) / prices[i - self.lookback]
        
        # Pad with NaN for initial values
        momentum[:self.lookback] = np.nan
        
        # Compute statistics on valid values
        valid_momentum = momentum[~np.isnan(momentum)]
        stats = self.compute_statistics(valid_momentum)
        
        return SignalResult(
            signal_name=self.metadata.signal_name,
            values=momentum,
            timestamps=timestamps,
            metadata=self.metadata,
            mean=stats['mean'],
            std=stats['std'],
            min=stats['min'],
            max=stats['max']
        )


class EWMA_MomentumSignal(BaseSignal):
    """
    Exponentially weighted moving average momentum signal.
    
    Uses EWMA to give more weight to recent price changes.
    """
    
    def __init__(self, lookback: int = 20, alpha: float = 0.1):
        metadata = SignalMetadata(
            signal_name="ewma_momentum",
            category=SignalCategory.MOMENTUM,
            horizon=SignalHorizon.SHORT,
            description="EWMA momentum signal with exponential weighting",
            parameters={'lookback': lookback, 'alpha': alpha}
        )
        super().__init__(metadata)
        self.lookback = lookback
        self.alpha = alpha
    
    def compute(self, prices: np.ndarray, timestamps: np.ndarray, **kwargs) -> SignalResult:
        """Compute EWMA momentum signal."""
        self.validate_inputs(prices, timestamps)
        
        if len(prices) < self.lookback + 1:
            raise ValueError(f"Need at least {self.lookback + 1} prices")
        
        # Compute EWMA momentum
        momentum = np.zeros(len(prices))
        ewma = prices[0]
        
        for i in range(1, len(prices)):
            ewma = self.alpha * prices[i] + (1 - self.alpha) * ewma
            if i >= self.lookback:
                momentum[i] = (prices[i] - ewma) / ewma
        
        momentum[:self.lookback] = np.nan
        
        valid_momentum = momentum[~np.isnan(momentum)]
        stats = self.compute_statistics(valid_momentum)
        
        return SignalResult(
            signal_name=self.metadata.signal_name,
            values=momentum,
            timestamps=timestamps,
            metadata=self.metadata,
            mean=stats['mean'],
            std=stats['std'],
            min=stats['min'],
            max=stats['max']
        )


# ============================================================================
# MEAN REVERSION SIGNALS
# ============================================================================

class ZScoreSignal(BaseSignal):
    """
    Z-score mean reversion signal.
    
    Measures how many standard deviations price is from its mean.
    High z-scores indicate overbought, low z-scores indicate oversold.
    """
    
    def __init__(self, lookback: int = 20):
        metadata = SignalMetadata(
            signal_name="zscore",
            category=SignalCategory.MEAN_REVERSION,
            horizon=SignalHorizon.SHORT,
            description="Z-score mean reversion signal",
            parameters={'lookback': lookback}
        )
        super().__init__(metadata)
        self.lookback = lookback
    
    def compute(self, prices: np.ndarray, timestamps: np.ndarray, **kwargs) -> SignalResult:
        """Compute z-score signal."""
        self.validate_inputs(prices, timestamps)
        
        if len(prices) < self.lookback:
            raise ValueError(f"Need at least {self.lookback} prices")
        
        zscore = np.zeros(len(prices))
        
        for i in range(self.lookback, len(prices)):
            window = prices[i - self.lookback:i]
            mean = np.mean(window)
            std = np.std(window)
            if std > 0:
                zscore[i] = (prices[i] - mean) / std
        
        zscore[:self.lookback] = np.nan
        
        valid_zscore = zscore[~np.isnan(zscore)]
        stats = self.compute_statistics(valid_zscore)
        
        return SignalResult(
            signal_name=self.metadata.signal_name,
            values=zscore,
            timestamps=timestamps,
            metadata=self.metadata,
            mean=stats['mean'],
            std=stats['std'],
            min=stats['min'],
            max=stats['max']
        )


class RSISignal(BaseSignal):
    """
    Relative Strength Index (RSI) signal.
    
    RSI measures momentum and identifies overbought/oversold conditions.
    Range: 0-100, with >70 overbought and <30 oversold.
    """
    
    def __init__(self, period: int = 14):
        metadata = SignalMetadata(
            signal_name="rsi",
            category=SignalCategory.MOMENTUM,
            horizon=SignalHorizon.SHORT,
            description="Relative Strength Index (RSI) signal",
            parameters={'period': period}
        )
        super().__init__(metadata)
        self.period = period
    
    def compute(self, prices: np.ndarray, timestamps: np.ndarray, **kwargs) -> SignalResult:
        """Compute RSI signal."""
        self.validate_inputs(prices, timestamps)
        
        if len(prices) < self.period + 1:
            raise ValueError(f"Need at least {self.period + 1} prices")
        
        # Compute price changes
        deltas = np.diff(prices)
        
        # Separate gains and losses
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        # Compute average gains and losses
        avg_gains = np.zeros(len(prices))
        avg_losses = np.zeros(len(prices))
        
        # Initial average
        avg_gains[self.period] = np.mean(gains[:self.period])
        avg_losses[self.period] = np.mean(losses[:self.period])
        
        # Exponential smoothing
        for i in range(self.period + 1, len(prices)):
            avg_gains[i] = (avg_gains[i - 1] * (self.period - 1) + gains[i - 1]) / self.period
            avg_losses[i] = (avg_losses[i - 1] * (self.period - 1) + losses[i - 1]) / self.period
        
        # Compute RSI
        rsi = np.zeros(len(prices))
        for i in range(self.period, len(prices)):
            if avg_losses[i] == 0:
                rsi[i] = 100
            else:
                rs = avg_gains[i] / avg_losses[i]
                rsi[i] = 100 - (100 / (1 + rs))
        
        rsi[:self.period] = np.nan
        
        valid_rsi = rsi[~np.isnan(rsi)]
        stats = self.compute_statistics(valid_rsi)
        
        return SignalResult(
            signal_name=self.metadata.signal_name,
            values=rsi,
            timestamps=timestamps,
            metadata=self.metadata,
            mean=stats['mean'],
            std=stats['std'],
            min=stats['min'],
            max=stats['max']
        )


# ============================================================================
# TREND SIGNALS
# ============================================================================

class MovingAverageCrossoverSignal(BaseSignal):
    """
    Moving average crossover signal.
    
    Generates signals when short MA crosses above/below long MA.
    """
    
    def __init__(self, short_period: int = 10, long_period: int = 30):
        metadata = SignalMetadata(
            signal_name="ma_crossover",
            category=SignalCategory.TREND,
            horizon=SignalHorizon.MEDIUM,
            description="Moving average crossover trend signal",
            parameters={'short_period': short_period, 'long_period': long_period}
        )
        super().__init__(metadata)
        self.short_period = short_period
        self.long_period = long_period
    
    def compute(self, prices: np.ndarray, timestamps: np.ndarray, **kwargs) -> SignalResult:
        """Compute MA crossover signal."""
        self.validate_inputs(prices, timestamps)
        
        if len(prices) < self.long_period:
            raise ValueError(f"Need at least {self.long_period} prices")
        
        # Compute moving averages
        short_ma = np.convolve(prices, np.ones(self.short_period)/self.short_period, mode='valid')
        long_ma = np.convolve(prices, np.ones(self.long_period)/self.long_period, mode='valid')
        
        # Align arrays
        signal = np.zeros(len(prices))
        signal[:self.long_period] = np.nan
        
        for i in range(self.long_period, len(prices)):
            short_idx = i - self.long_period
            long_idx = i - self.long_period
            
            if short_idx < len(short_ma) and long_idx < len(long_ma):
                if short_ma[short_idx] > long_ma[long_idx]:
                    signal[i] = 1  # Bullish
                elif short_ma[short_idx] < long_ma[long_idx]:
                    signal[i] = -1  # Bearish
                else:
                    signal[i] = 0  # Neutral
        
        valid_signal = signal[~np.isnan(signal)]
        stats = self.compute_statistics(valid_signal)
        
        return SignalResult(
            signal_name=self.metadata.signal_name,
            values=signal,
            timestamps=timestamps,
            metadata=self.metadata,
            mean=stats['mean'],
            std=stats['std'],
            min=stats['min'],
            max=stats['max']
        )


# ============================================================================
# VOLATILITY SIGNALS
# ============================================================================

class RollingVolatilitySignal(BaseSignal):
    """
    Rolling volatility signal.
    
    Measures price volatility over a rolling window.
    """
    
    def __init__(self, lookback: int = 20):
        metadata = SignalMetadata(
            signal_name="rolling_volatility",
            category=SignalCategory.VOLATILITY,
            horizon=SignalHorizon.SHORT,
            description="Rolling volatility signal",
            parameters={'lookback': lookback}
        )
        super().__init__(metadata)
        self.lookback = lookback
    
    def compute(self, prices: np.ndarray, timestamps: np.ndarray, **kwargs) -> SignalResult:
        """Compute rolling volatility signal."""
        self.validate_inputs(prices, timestamps)
        
        if len(prices) < self.lookback:
            raise ValueError(f"Need at least {self.lookback} prices")
        
        # Compute returns
        returns = np.diff(np.log(prices))
        
        # Compute rolling volatility
        volatility = np.zeros(len(prices))
        volatility[:self.lookback] = np.nan
        
        for i in range(self.lookback, len(prices)):
            window_returns = returns[i - self.lookback:i]
            volatility[i] = np.std(window_returns) * np.sqrt(252)  # Annualized
        
        valid_vol = volatility[~np.isnan(volatility)]
        stats = self.compute_statistics(valid_vol)
        
        return SignalResult(
            signal_name=self.metadata.signal_name,
            values=volatility,
            timestamps=timestamps,
            metadata=self.metadata,
            mean=stats['mean'],
            std=stats['std'],
            min=stats['min'],
            max=stats['max']
        )


# ============================================================================
# SIGNAL LIBRARY
# ============================================================================

class SignalLibrary:
    """
    Comprehensive signal library for DELTA.
    
    Provides access to all signal types with a unified interface.
    """
    
    def __init__(self):
        self._signals: Dict[str, BaseSignal] = {}
        self._register_default_signals()
    
    def _register_default_signals(self):
        """Register default signal implementations."""
        # Momentum signals
        self.register('simple_momentum_20', SimpleMomentumSignal(lookback=20))
        self.register('simple_momentum_50', SimpleMomentumSignal(lookback=50))
        self.register('ewma_momentum_20', EWMA_MomentumSignal(lookback=20, alpha=0.1))
        
        # Mean reversion signals
        self.register('zscore_20', ZScoreSignal(lookback=20))
        self.register('zscore_50', ZScoreSignal(lookback=50))
        self.register('rsi_14', RSISignal(period=14))
        
        # Trend signals
        self.register('ma_crossover_10_30', MovingAverageCrossoverSignal(short_period=10, long_period=30))
        self.register('ma_crossover_20_50', MovingAverageCrossoverSignal(short_period=20, long_period=50))
        
        # Volatility signals
        self.register('rolling_volatility_20', RollingVolatilitySignal(lookback=20))
        self.register('rolling_volatility_50', RollingVolatilitySignal(lookback=50))
    
    def register(self, name: str, signal: BaseSignal) -> None:
        """Register a signal with the library."""
        self._signals[name] = signal
    
    def get(self, name: str) -> Optional[BaseSignal]:
        """Get a signal by name."""
        return self._signals.get(name)
    
    def list_signals(self) -> List[str]:
        """List all registered signal names."""
        return list(self._signals.keys())
    
    def compute(self, name: str, prices: np.ndarray, timestamps: np.ndarray, **kwargs) -> SignalResult:
        """
        Compute a signal by name.
        
        Args:
            name: Signal name
            prices: Price series
            timestamps: Timestamp series
            **kwargs: Additional parameters
            
        Returns:
            SignalResult
        """
        signal = self.get(name)
        if signal is None:
            raise ValueError(f"Signal '{name}' not found. Available: {self.list_signals()}")
        
        return signal.compute(prices, timestamps, **kwargs)
    
    def compute_multiple(self, names: List[str], prices: np.ndarray, timestamps: np.ndarray, **kwargs) -> Dict[str, SignalResult]:
        """
        Compute multiple signals.
        
        Args:
            names: List of signal names
            prices: Price series
            timestamps: Timestamp series
            **kwargs: Additional parameters
            
        Returns:
            Dictionary of signal results
        """
        results = {}
        for name in names:
            try:
                results[name] = self.compute(name, prices, timestamps, **kwargs)
            except Exception as e:
                print(f"Error computing signal {name}: {e}")
        return results


# Global signal library instance
_signal_library: Optional[SignalLibrary] = None


def get_signal_library() -> SignalLibrary:
    """Get the global signal library instance."""
    global _signal_library
    if _signal_library is None:
        _signal_library = SignalLibrary()
    return _signal_library


# Convenience functions for backward compatibility
def rsi(prices, period: int = 14):
    """
    Compute RSI values (convenience function).
    
    Args:
        prices: Price series (can be tuple of Decimal or numpy array)
        period: RSI period
        
    Returns:
        RSI values (single Decimal for tuple input, numpy array for array input)
    """
    # Handle Decimal tuple input for backward compatibility
    if isinstance(prices, tuple) and len(prices) > 0:
        from decimal import Decimal
        if isinstance(prices[0], Decimal):
            prices_np = np.array([float(p) for p in prices])
        else:
            prices_np = np.array(prices)
    else:
        prices_np = np.array(prices)
    
    signal = RSISignal(period=period)
    timestamps = np.arange(len(prices_np))
    result = signal.compute(prices_np, timestamps)
    
    # Return single Decimal for backward compatibility if input was tuple
    if isinstance(prices, tuple) and len(prices) > 0 and isinstance(prices[0], Decimal):
        from decimal import Decimal
        # Return the last valid RSI value
        valid_values = [Decimal(str(v)) for v in result.values if not np.isnan(v)]
        return valid_values[-1] if valid_values else Decimal("0")
    
    return result.values


def momentum(prices, lookback: int = 20):
    """
    Compute momentum values (convenience function).
    
    Args:
        prices: Price series (can be tuple of Decimal or numpy array)
        lookback: Lookback period
        
    Returns:
        Momentum values (single Decimal for tuple input, numpy array for array input)
    """
    # Handle Decimal tuple input for backward compatibility
    if isinstance(prices, tuple) and len(prices) > 0:
        from decimal import Decimal
        if isinstance(prices[0], Decimal):
            prices_np = np.array([float(p) for p in prices])
        else:
            prices_np = np.array(prices)
    else:
        prices_np = np.array(prices)
    
    signal = SimpleMomentumSignal(lookback=lookback)
    timestamps = np.arange(len(prices_np))
    result = signal.compute(prices_np, timestamps)
    
    # Return single Decimal for backward compatibility if input was tuple
    if isinstance(prices, tuple) and len(prices) > 0 and isinstance(prices[0], Decimal):
        from decimal import Decimal
        # Return the last valid momentum value
        valid_values = [Decimal(str(v)) for v in result.values if not np.isnan(v)]
        return valid_values[-1] if valid_values else Decimal("0")
    
    return result.values


__all__ = [
    'SignalCategory',
    'SignalHorizon',
    'SignalMetadata',
    'SignalResult',
    'BaseSignal',
    'SimpleMomentumSignal',
    'EWMA_MomentumSignal',
    'ZScoreSignal',
    'RSISignal',
    'MovingAverageCrossoverSignal',
    'RollingVolatilitySignal',
    'SignalLibrary',
    'get_signal_library',
    'rsi',
    'momentum',
]