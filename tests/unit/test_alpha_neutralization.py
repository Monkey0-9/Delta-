"""
Unit tests for Alpha Neutralization Pipeline.
"""

import pytest
import pandas as pd
import numpy as np
from decimal import Decimal

from quant.alpha.neutralization import (
    AlphaNeutralizer,
    NeutralizationConfig,
    NeutralizationResult,
    NeutralizationType,
    FactorType,
)
from core.contracts.canonical import (
    Instrument,
    AssetClass,
    Currency,
)


def test_alpha_neutralizer_initialization():
    """Test alpha neutralizer initialization."""
    config = NeutralizationConfig(
        neutralization_types=[NeutralizationType.BETA, NeutralizationType.SIZE],
        standardize=True
    )
    
    neutralizer = AlphaNeutralizer(config)
    
    assert neutralizer._config == config


def test_beta_neutralization():
    """Test beta neutralization."""
    neutralizer = AlphaNeutralizer(
        NeutralizationConfig(neutralization_types=[NeutralizationType.BETA])
    )
    
    # Create sample alpha and beta data
    instruments = [
        Instrument(symbol="AAPL", asset_class=AssetClass.EQUITY, currency=Currency.USD),
        Instrument(symbol="MSFT", asset_class=AssetClass.EQUITY, currency=Currency.USD),
        Instrument(symbol="GOOGL", asset_class=AssetClass.EQUITY, currency=Currency.USD),
    ]
    
    alpha = pd.Series([0.05, 0.03, 0.07], index=["AAPL", "MSFT", "GOOGL"])
    
    factor_matrix = pd.DataFrame({
        "beta": pd.Series([1.2, 1.0, 0.8], index=["AAPL", "MSFT", "GOOGL"]),
    })
    
    result = neutralizer._neutralize_beta(alpha, factor_matrix)
    
    # Result should be a Series
    assert isinstance(result, pd.Series)
    assert len(result) == len(alpha)


def test_industry_neutralization():
    """Test industry neutralization."""
    neutralizer = AlphaNeutralizer(
        NeutralizationConfig(neutralization_types=[NeutralizationType.INDUSTRY])
    )
    
    instruments = [
        Instrument(symbol="AAPL", asset_class=AssetClass.EQUITY, currency=Currency.USD),
        Instrument(symbol="MSFT", asset_class=AssetClass.EQUITY, currency=Currency.USD),
        Instrument(symbol="JPM", asset_class=AssetClass.EQUITY, currency=Currency.USD),
    ]
    
    alpha = pd.Series([0.05, 0.03, 0.02], index=["AAPL", "MSFT", "JPM"])
    
    metadata = {
        "industry": pd.Series(
            ["Technology", "Technology", "Financials"],
            index=["AAPL", "MSFT", "JPM"]
        )
    }
    
    result = neutralizer._neutralize_industry(alpha, instruments, metadata)
    
    # Technology stocks should have neutralized alpha
    assert isinstance(result, pd.Series)
    assert len(result) == len(alpha)


def test_full_neutralization():
    """Test full neutralization pipeline."""
    neutralizer = AlphaNeutralizer(
        NeutralizationConfig(
            neutralization_types=[NeutralizationType.BETA, NeutralizationType.SIZE],
            standardize=True
        )
    )
    
    instruments = [
        Instrument(symbol="AAPL", asset_class=AssetClass.EQUITY, currency=Currency.USD),
        Instrument(symbol="MSFT", asset_class=AssetClass.EQUITY, currency=Currency.USD),
        Instrument(symbol="GOOGL", asset_class=AssetClass.EQUITY, currency=Currency.USD),
    ]
    
    alpha = pd.Series([0.05, 0.03, 0.07], index=["AAPL", "MSFT", "GOOGL"])
    
    metadata = {
        "beta": pd.Series([1.2, 1.0, 0.8], index=["AAPL", "MSFT", "GOOGL"]),
        "market_cap": pd.Series([2.5e12, 2.0e12, 1.5e12], index=["AAPL", "MSFT", "GOOGL"]),
    }
    
    result = neutralizer.neutralize(alpha, instruments, metadata)
    
    assert isinstance(result, NeutralizationResult)
    assert len(result.neutralized_alpha) == len(alpha)
    assert result.r_squared >= 0.0
    assert result.r_squared <= 1.0


def test_winsorization():
    """Test winsorization."""
    neutralizer = AlphaNeutralizer(
        NeutralizationConfig(
            winsorize_threshold=0.1,
            standardize=False
        )
    )
    
    alpha = pd.Series([0.1, 0.05, 0.03, 0.02, -0.05, -0.1])
    
    winsorized = neutralizer._winsorize(alpha, 0.1)
    
    # Values should be clipped
    assert winsorized.min() >= alpha.quantile(0.1)
    assert winsorized.max() <= alpha.quantile(0.9)


def test_standardization():
    """Test standardization."""
    neutralizer = AlphaNeutralizer(
        NeutralizationConfig(standardize=True)
    )
    
    alpha = pd.Series([0.05, 0.03, 0.07, 0.02, 0.04])
    
    standardized = neutralizer._standardize(alpha)
    
    # Mean should be ~0, std should be ~1
    assert abs(standardized.mean()) < 1e-10
    assert abs(standardized.std() - 1.0) < 1e-10


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
