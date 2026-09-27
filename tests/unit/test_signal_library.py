"""
Tests for DELTA comprehensive signal library.
"""

import numpy as np
import pytest

from quant.signals.signal_library import (
    SignalCategory,
    SignalHorizon,
    SignalMetadata,
    SignalResult,
    BaseSignal,
    SimpleMomentumSignal,
    EWMA_MomentumSignal,
    ZScoreSignal,
    RSISignal,
    MovingAverageCrossoverSignal,
    RollingVolatilitySignal,
    SignalLibrary,
    get_signal_library,
)


class TestSignalMetadata:
    """Test signal metadata."""
    
    def test_metadata_creation(self):
        """Test basic metadata creation."""
        metadata = SignalMetadata(
            signal_name="test_signal",
            category=SignalCategory.MOMENTUM,
            horizon=SignalHorizon.SHORT,
            description="Test signal"
        )
        
        assert metadata.signal_name == "test_signal"
        assert metadata.category == SignalCategory.MOMENTUM
        assert metadata.horizon == SignalHorizon.SHORT
        assert metadata.version == "1.0.0"
    
    def test_metadata_to_dict(self):
        """Test metadata serialization."""
        metadata = SignalMetadata(
            signal_name="test_signal",
            category=SignalCategory.MOMENTUM,
            horizon=SignalHorizon.SHORT,
            description="Test signal"
        )
        
        metadata_dict = metadata.to_dict()
        
        assert metadata_dict['signal_name'] == "test_signal"
        assert metadata_dict['category'] == "momentum"
        assert metadata_dict['horizon'] == "short"


class TestSimpleMomentumSignal:
    """Test simple momentum signal."""
    
    def test_momentum_computation(self):
        """Test momentum signal computation."""
        signal = SimpleMomentumSignal(lookback=5)
        
        prices = np.array([100.0, 101.0, 102.0, 103.0, 104.0, 105.0, 106.0])
        timestamps = np.arange(len(prices))
        
        result = signal.compute(prices, timestamps)
        
        assert result.signal_name == "simple_momentum"
        assert len(result.values) == len(prices)
        assert np.isnan(result.values[4])  # First 5 values should be NaN
        assert not np.isnan(result.values[5])  # Should have value after lookback
        assert result.values[5] > 0  # Positive momentum
    
    def test_momentum_validation(self):
        """Test input validation."""
        signal = SimpleMomentumSignal(lookback=5)
        
        # Empty prices
        with pytest.raises(ValueError):
            signal.compute(np.array([]), np.array([]))
        
        # Negative prices
        with pytest.raises(ValueError):
            signal.compute(np.array([100.0, -50.0]), np.array([0, 1]))


class TestEWMA_MomentumSignal:
    """Test EWMA momentum signal."""
    
    def test_ewma_momentum_computation(self):
        """Test EWMA momentum computation."""
        signal = EWMA_MomentumSignal(lookback=5, alpha=0.1)
        
        prices = np.array([100.0, 101.0, 102.0, 103.0, 104.0, 105.0, 106.0])
        timestamps = np.arange(len(prices))
        
        result = signal.compute(prices, timestamps)
        
        assert result.signal_name == "ewma_momentum"
        assert len(result.values) == len(prices)
        assert np.isnan(result.values[4])  # First 5 values should be NaN


class TestZScoreSignal:
    """Test z-score signal."""
    
    def test_zscore_computation(self):
        """Test z-score computation."""
        signal = ZScoreSignal(lookback=5)
        
        prices = np.array([100.0, 101.0, 102.0, 103.0, 104.0, 105.0, 106.0])
        timestamps = np.arange(len(prices))
        
        result = signal.compute(prices, timestamps)
        
        assert result.signal_name == "zscore"
        assert len(result.values) == len(prices)
        assert np.isnan(result.values[4])  # First 5 values should be NaN


class TestRSISignal:
    """Test RSI signal."""
    
    def test_rsi_computation(self):
        """Test RSI computation."""
        signal = RSISignal(period=14)
        
        # Create trending price series
        prices = np.linspace(100, 150, 30)
        timestamps = np.arange(len(prices))
        
        result = signal.compute(prices, timestamps)
        
        assert result.signal_name == "rsi"
        assert len(result.values) == len(prices)
        assert np.isnan(result.values[13])  # First 14 values should be NaN
        assert not np.isnan(result.values[14])  # Should have value after period


class TestMovingAverageCrossoverSignal:
    """Test moving average crossover signal."""
    
    def test_ma_crossover_computation(self):
        """Test MA crossover computation."""
        signal = MovingAverageCrossoverSignal(short_period=5, long_period=10)
        
        prices = np.linspace(100, 150, 30)
        timestamps = np.arange(len(prices))
        
        result = signal.compute(prices, timestamps)
        
        assert result.signal_name == "ma_crossover"
        assert len(result.values) == len(prices)
        assert np.isnan(result.values[9])  # First 10 values should be NaN


class TestRollingVolatilitySignal:
    """Test rolling volatility signal."""
    
    def test_rolling_volatility_computation(self):
        """Test rolling volatility computation."""
        signal = RollingVolatilitySignal(lookback=10)
        
        prices = np.linspace(100, 150, 30)
        timestamps = np.arange(len(prices))
        
        result = signal.compute(prices, timestamps)
        
        assert result.signal_name == "rolling_volatility"
        assert len(result.values) == len(prices)
        assert np.isnan(result.values[9])  # First 10 values should be NaN
        assert not np.isnan(result.values[10])  # Should have value after lookback


class TestSignalLibrary:
    """Test signal library."""
    
    def test_library_creation(self):
        """Test library instance creation."""
        library = SignalLibrary()
        
        assert library is not None
        assert len(library.list_signals()) > 0
    
    def test_default_signals_registered(self):
        """Test that default signals are registered."""
        library = SignalLibrary()
        
        signals = library.list_signals()
        
        assert 'simple_momentum_20' in signals
        assert 'zscore_20' in signals
        assert 'rsi_14' in signals
    
    def test_get_signal(self):
        """Test getting a signal from library."""
        library = SignalLibrary()
        
        signal = library.get('simple_momentum_20')
        
        assert signal is not None
        assert isinstance(signal, SimpleMomentumSignal)
    
    def test_compute_signal(self):
        """Test computing a signal through library."""
        library = SignalLibrary()
        
        prices = np.linspace(100, 150, 30)
        timestamps = np.arange(len(prices))
        
        result = library.compute('simple_momentum_20', prices, timestamps)
        
        assert result.signal_name == "simple_momentum"
        assert len(result.values) == len(prices)
    
    def test_compute_multiple_signals(self):
        """Test computing multiple signals."""
        library = SignalLibrary()
        
        prices = np.linspace(100, 150, 30)
        timestamps = np.arange(len(prices))
        
        results = library.compute_multiple(
            ['simple_momentum_20', 'zscore_20'],
            prices,
            timestamps
        )
        
        assert 'simple_momentum_20' in results
        assert 'zscore_20' in results
        assert len(results) == 2
    
    def test_global_library(self):
        """Test global library instance."""
        library1 = get_signal_library()
        library2 = get_signal_library()
        
        assert library1 is library2
    
    def test_register_custom_signal(self):
        """Test registering a custom signal."""
        library = SignalLibrary()
        
        custom_signal = SimpleMomentumSignal(lookback=10)
        library.register('custom_momentum', custom_signal)
        
        retrieved = library.get('custom_momentum')
        assert retrieved is custom_signal