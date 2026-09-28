"""
Alpha Neutralization Pipeline for Institutional-Grade Quant Research.

This module implements sophisticated alpha neutralization techniques:
- Industry neutralization
- Sector neutralization
- Beta neutralization
- Volatility neutralization
- Size neutralization
- Factor orthogonalization
- Residualization

Neutralization is critical for:
- Removing common risk factors
- Isolating pure alpha
- Reducing factor exposure
- Improving signal quality
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Optional, Dict, List, Tuple, Union
import numpy as np
import pandas as pd
from scipy import stats
from sklearn.linear_model import LinearRegression

from core.contracts.canonical import Instrument, AssetClass, Currency


class NeutralizationType(Enum):
    """Types of neutralization."""
    INDUSTRY = "industry"  # Neutralize industry factors
    SECTOR = "sector"  # Neutralize sector factors
    BETA = "beta"  # Neutralize market beta
    VOLATILITY = "volatility"  # Neutralize volatility
    SIZE = "size"  # Neutralize market cap
    FACTOR = "factor"  # Neutralize specific factors
    ORTHOGONAL = "orthogonal"  # Orthogonalize against factors
    RESIDUAL = "residual"  # Regression residualization


class FactorType(Enum):
    """Common factor types."""
    MARKET = "market"  # Market factor
    SIZE = "size"  # Size factor
    VALUE = "value"  # Value factor
    MOMENTUM = "momentum"  # Momentum factor
    VOLATILITY = "volatility"  # Volatility factor
    QUALITY = "quality"  # Quality factor
    GROWTH = "growth"  # Growth factor
    LEVERAGE = "leverage"  # Leverage factor


@dataclass(frozen=True, slots=True)
class NeutralizationConfig:
    """
    Configuration for alpha neutralization.
    
    Attributes:
        neutralization_types: Types of neutralization to apply
        factor_types: Factor types to neutralize against
        min_observations: Minimum observations for regression
        regression_method: Regression method (OLS, WLS, etc.)
        winsorize_threshold: Winsorization threshold (None = no winsorization)
        standardize: Whether to standardize results
        orthogonalize: Whether to orthogonalize factors
        residualize: Whether to use residualization
    """
    neutralization_types: List[NeutralizationType] = field(default_factory=list)
    factor_types: List[FactorType] = field(default_factory=list)
    min_observations: int = 20
    regression_method: str = "OLS"  # OLS, WLS, Ridge, Lasso
    winsorize_threshold: Optional[float] = None  # e.g., 0.05 for 5% winsorization
    standardize: bool = True
    orthogonalize: bool = False
    residualize: bool = True


@dataclass
class NeutralizationResult:
    """
    Result of alpha neutralization.
    
    Attributes:
        original_alpha: Original alpha values
        neutralized_alpha: Neutralized alpha values
        neutralization_factors: Factors used for neutralization
        factor_exposures: Exposure to each factor
        residuals: Regression residuals
        r_squared: R-squared of regression
        timestamp: When neutralization was performed
        metadata: Additional metadata
    """
    original_alpha: pd.Series
    neutralized_alpha: pd.Series
    neutralization_factors: pd.DataFrame
    factor_exposures: Dict[str, float]
    residuals: pd.Series
    r_squared: float
    timestamp: datetime
    metadata: Dict = field(default_factory=dict)
    
    @property
    def reduction_ratio(self) -> float:
        """Ratio of variance reduction."""
        original_var = self.original_alpha.var()
        neutralized_var = self.neutralized_alpha.var()
        if original_var == 0:
            return 0.0
        return 1.0 - (neutralized_var / original_var)
    
    @property
    def information_ratio(self) -> float:
        """Information ratio (mean / std)."""
        mean = self.neutralized_alpha.mean()
        std = self.neutralized_alpha.std()
        if std == 0:
            return 0.0
        return mean / std


class AlphaNeutralizer:
    """
    Alpha neutralization pipeline for institutional-grade research.
    
    Features:
    - Multiple neutralization types
    - Factor exposure calculation
    - Regression-based residualization
    - Winsorization and standardization
    - Factor orthogonalization
    - Performance metrics
    """
    
    # Typical industry classifications (simplified)
    INDUSTRY_MAPPING: Dict[str, str] = {
        "Technology": "Technology",
        "Financials": "Financials",
        "Healthcare": "Healthcare",
        "Consumer": "Consumer",
        "Energy": "Energy",
        "Industrial": "Industrial",
        "Materials": "Materials",
        "Utilities": "Utilities",
        "Real Estate": "Real Estate",
        "Communication": "Communication",
    }
    
    # Typical sector classifications
    SECTOR_MAPPING: Dict[str, str] = {
        "Technology": "Cyclical",
        "Financials": "Financial",
        "Healthcare": "Defensive",
        "Consumer": "Cyclical",
        "Energy": "Cyclical",
        "Industrial": "Cyclical",
        "Materials": "Cyclical",
        "Utilities": "Defensive",
        "Real Estate": "Financial",
        "Communication": "Cyclical",
    }
    
    def __init__(self, config: Optional[NeutralizationConfig] = None):
        """
        Initialize alpha neutralizer.
        
        Args:
            config: Neutralization configuration
        """
        self._config = config or NeutralizationConfig()
        self._factor_data: Dict[str, pd.DataFrame] = {}
        
    def add_factor_data(self, factor_type: FactorType, data: pd.DataFrame) -> None:
        """
        Add factor data for neutralization.
        
        Args:
            factor_type: Type of factor
            data: Factor data (instrument -> factor value)
        """
        self._factor_data[factor_type.value] = data
    
    def neutralize(
        self,
        alpha: pd.Series,
        instruments: List[Instrument],
        metadata: Optional[Dict[str, pd.Series]] = None
    ) -> NeutralizationResult:
        """
        Neutralize alpha signal.
        
        Args:
            alpha: Alpha values (instrument -> alpha)
            instruments: List of instruments
            metadata: Additional metadata (industry, sector, market_cap, etc.)
            
        Returns:
            NeutralizationResult with neutralized alpha
        """
        if metadata is None:
            metadata = {}
        
        original_alpha = alpha.copy()
        neutralized_alpha = alpha.copy()
        
        # Build factor matrix
        factor_matrix = self._build_factor_matrix(instruments, metadata)
        
        # Apply neutralization types
        for neutralization_type in self._config.neutralization_types:
            if neutralization_type == NeutralizationType.INDUSTRY:
                neutralized_alpha = self._neutralize_industry(
                    neutralized_alpha, instruments, metadata
                )
            elif neutralization_type == NeutralizationType.SECTOR:
                neutralized_alpha = self._neutralize_sector(
                    neutralized_alpha, instruments, metadata
                )
            elif neutralization_type == NeutralizationType.BETA:
                neutralized_alpha = self._neutralize_beta(
                    neutralized_alpha, factor_matrix
                )
            elif neutralization_type == NeutralizationType.VOLATILITY:
                neutralized_alpha = self._neutralize_volatility(
                    neutralized_alpha, factor_matrix
                )
            elif neutralization_type == NeutralizationType.SIZE:
                neutralized_alpha = self._neutralize_size(
                    neutralized_alpha, factor_matrix
                )
            elif neutralization_type == NeutralizationType.FACTOR:
                neutralized_alpha = self._neutralize_factors(
                    neutralized_alpha, factor_matrix
                )
            elif neutralization_type == NeutralizationType.ORTHOGONAL:
                neutralized_alpha = self._orthogonalize(
                    neutralized_alpha, factor_matrix
                )
            elif neutralization_type == NeutralizationType.RESIDUAL:
                neutralized_alpha = self._residualize(
                    neutralized_alpha, factor_matrix
                )
        
        # Winsorize if configured
        if self._config.winsorize_threshold is not None:
            neutralized_alpha = self._winsorize(
                neutralized_alpha, self._config.winsorize_threshold
            )
        
        # Standardize if configured
        if self._config.standardize:
            neutralized_alpha = self._standardize(neutralized_alpha)
        
        # Calculate factor exposures
        factor_exposures = self._calculate_factor_exposures(
            original_alpha, neutralized_alpha, factor_matrix
        )
        
        # Calculate residuals and R-squared
        residuals = original_alpha - neutralized_alpha
        r_squared = self._calculate_r_squared(original_alpha, neutralized_alpha)
        
        return NeutralizationResult(
            original_alpha=original_alpha,
            neutralized_alpha=neutralized_alpha,
            neutralization_factors=factor_matrix,
            factor_exposures=factor_exposures,
            residuals=residuals,
            r_squared=r_squared,
            timestamp=datetime.now(timezone.utc),
            metadata={
                "config": self._config,
                "instruments": [i.symbol for i in instruments],
            }
        )
    
    def _build_factor_matrix(
        self,
        instruments: List[Instrument],
        metadata: Dict[str, pd.Series]
    ) -> pd.DataFrame:
        """
        Build factor matrix for neutralization.
        
        Args:
            instruments: List of instruments
            metadata: Metadata for instruments
            
        Returns:
            DataFrame with factor values
        """
        factors = {}
        
        # Add market factor (constant)
        factors["market"] = pd.Series(1.0, index=[i.symbol for i in instruments])
        
        # Add factor data if available
        for factor_type in self._config.factor_types:
            if factor_type.value in self._factor_data:
                factor_data = self._factor_data[factor_type.value]
                factors[factor_type.value] = factor_data.reindex(
                    [i.symbol for i in instruments]
                ).fillna(0.0)
        
        # Add metadata factors
        if "market_cap" in metadata:
            factors["size"] = metadata["market_cap"].reindex(
                [i.symbol for i in instruments]
            ).fillna(0.0)
        
        if "beta" in metadata:
            factors["beta"] = metadata["beta"].reindex(
                [i.symbol for i in instruments]
            ).fillna(1.0)
        
        if "volatility" in metadata:
            factors["volatility"] = metadata["volatility"].reindex(
                [i.symbol for i in instruments]
            ).fillna(0.2)
        
        return pd.DataFrame(factors)
    
    def _neutralize_industry(
        self,
        alpha: pd.Series,
        instruments: List[Instrument],
        metadata: Dict[str, pd.Series]
    ) -> pd.Series:
        """Neutralize industry factors."""
        if "industry" not in metadata:
            return alpha
        
        industry_series = metadata["industry"].reindex(alpha.index)
        
        # Calculate industry means
        industry_means = alpha.groupby(industry_series).transform("mean")
        
        # Subtract industry means
        neutralized = alpha - industry_means
        
        return neutralized
    
    def _neutralize_sector(
        self,
        alpha: pd.Series,
        instruments: List[Instrument],
        metadata: Dict[str, pd.Series]
    ) -> pd.Series:
        """Neutralize sector factors."""
        if "sector" not in metadata:
            return alpha
        
        sector_series = metadata["sector"].reindex(alpha.index)
        
        # Calculate sector means
        sector_means = alpha.groupby(sector_series).transform("mean")
        
        # Subtract sector means
        neutralized = alpha - sector_means
        
        return neutralized
    
    def _neutralize_beta(
        self,
        alpha: pd.Series,
        factor_matrix: pd.DataFrame
    ) -> pd.Series:
        """Neutralize market beta."""
        if "beta" not in factor_matrix.columns:
            return alpha
        
        beta = factor_matrix["beta"]
        
        # Regress alpha on beta
        model = LinearRegression()
        X = beta.values.reshape(-1, 1)
        y = alpha.values
        
        mask = ~np.isnan(X.flatten()) & ~np.isnan(y)
        if mask.sum() < self._config.min_observations:
            return alpha
        
        model.fit(X[mask], y[mask])
        
        # Remove beta exposure
        neutralized = alpha - model.predict(X)
        
        return neutralized
    
    def _neutralize_volatility(
        self,
        alpha: pd.Series,
        factor_matrix: pd.DataFrame
    ) -> pd.Series:
        """Neutralize volatility."""
        if "volatility" not in factor_matrix.columns:
            return alpha
        
        volatility = factor_matrix["volatility"]
        
        # Regress alpha on volatility
        model = LinearRegression()
        X = volatility.values.reshape(-1, 1)
        y = alpha.values
        
        mask = ~np.isnan(X.flatten()) & ~np.isnan(y)
        if mask.sum() < self._config.min_observations:
            return alpha
        
        model.fit(X[mask], y[mask])
        
        # Remove volatility exposure
        neutralized = alpha - model.predict(X)
        
        return neutralized
    
    def _neutralize_size(
        self,
        alpha: pd.Series,
        factor_matrix: pd.DataFrame
    ) -> pd.Series:
        """Neutralize size (market cap)."""
        if "size" not in factor_matrix.columns:
            return alpha
        
        size = factor_matrix["size"]
        
        # Regress alpha on size
        model = LinearRegression()
        X = size.values.reshape(-1, 1)
        y = alpha.values
        
        mask = ~np.isnan(X.flatten()) & ~np.isnan(y)
        if mask.sum() < self._config.min_observations:
            return alpha
        
        model.fit(X[mask], y[mask])
        
        # Remove size exposure
        neutralized = alpha - model.predict(X)
        
        return neutralized
    
    def _neutralize_factors(
        self,
        alpha: pd.Series,
        factor_matrix: pd.DataFrame
    ) -> pd.Series:
        """Neutralize specified factors."""
        if factor_matrix.empty:
            return alpha
        
        # Select factor columns
        factor_cols = [col for col in factor_matrix.columns if col != "market"]
        if not factor_cols:
            return alpha
        
        X = factor_matrix[factor_cols].values
        y = alpha.values
        
        mask = ~np.isnan(X).any(axis=1) & ~np.isnan(y)
        if mask.sum() < self._config.min_observations:
            return alpha
        
        model = LinearRegression()
        model.fit(X[mask], y[mask])
        
        # Remove factor exposures
        neutralized = alpha - pd.Series(
            model.predict(X),
            index=alpha.index
        )
        
        return neutralized
    
    def _orthogonalize(
        self,
        alpha: pd.Series,
        factor_matrix: pd.DataFrame
    ) -> pd.Series:
        """Orthogonalize alpha against factors."""
        if factor_matrix.empty:
            return alpha
        
        # Gram-Schmidt orthogonalization
        orthogonalized = alpha.copy()
        
        for factor_col in factor_matrix.columns:
            factor = factor_matrix[factor_col]
            
            # Project alpha onto factor
            projection = (orthogonalized * factor).sum() / (factor ** 2).sum()
            
            # Remove projection
            orthogonalized = orthogonalized - projection * factor
        
        return orthogonalized
    
    def _residualize(
        self,
        alpha: pd.Series,
        factor_matrix: pd.DataFrame
    ) -> pd.Series:
        """Residualize alpha against factors."""
        if factor_matrix.empty:
            return alpha
        
        X = factor_matrix.values
        y = alpha.values
        
        mask = ~np.isnan(X).any(axis=1) & ~np.isnan(y)
        if mask.sum() < self._config.min_observations:
            return alpha
        
        model = LinearRegression()
        model.fit(X[mask], y[mask])
        
        # Return residuals
        residuals = pd.Series(
            y - model.predict(X),
            index=alpha.index
        )
        
        return residuals
    
    def _winsorize(self, alpha: pd.Series, threshold: float) -> pd.Series:
        """Winsorize alpha values."""
        lower = alpha.quantile(threshold)
        upper = alpha.quantile(1 - threshold)
        
        winsorized = alpha.clip(lower=lower, upper=upper)
        
        return winsorized
    
    def _standardize(self, alpha: pd.Series) -> pd.Series:
        """Standardize alpha values (z-score)."""
        mean = alpha.mean()
        std = alpha.std()
        
        if std == 0:
            return alpha - mean
        
        standardized = (alpha - mean) / std
        
        return standardized
    
    def _calculate_factor_exposures(
        self,
        original_alpha: pd.Series,
        neutralized_alpha: pd.Series,
        factor_matrix: pd.DataFrame
    ) -> Dict[str, float]:
        """Calculate factor exposures."""
        exposures = {}
        
        for factor_col in factor_matrix.columns:
            factor = factor_matrix[factor_col]
            
            # Calculate correlation (handle NaN)
            try:
                correlation = neutralized_alpha.corr(factor)
                if not np.isnan(correlation):
                    exposures[factor_col] = float(correlation)
            except Exception:
                # Skip if correlation calculation fails
                pass
        
        return exposures
    
    def _calculate_r_squared(
        self,
        original_alpha: pd.Series,
        neutralized_alpha: pd.Series
    ) -> float:
        """Calculate R-squared (variance explained by neutralization)."""
        # Calculate variance reduction
        original_var = original_alpha.var()
        neutralized_var = neutralized_alpha.var()
        
        if original_var == 0:
            return 0.0
        
        # R-squared as proportion of variance removed
        variance_explained = 1.0 - (neutralized_var / original_var)
        
        # Clamp to [0, 1]
        r_squared = max(0.0, min(1.0, variance_explained))
        
        return float(r_squared)


__all__ = [
    "NeutralizationType",
    "FactorType",
    "NeutralizationConfig",
    "NeutralizationResult",
    "AlphaNeutralizer",
]
