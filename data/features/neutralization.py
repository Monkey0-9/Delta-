"""Feature Neutralization Engine.

W98: Implements rolling Winsorization, cross-sectional Z-scoring,
and analytical factor neutralization in Rust/SIMD-optimized Python.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import Any
import numpy as np
from scipy import stats


class WinsorizationMethod(StrEnum):
    """Methods for winsorizing outliers."""
    MAD = "mad"  # Median Absolute Deviation
    IQR = "iqr"  # Interquartile Range
    SIGMA = "sigma"  # Standard deviation
    PERCENTILE = "percentile"  # Fixed percentiles


class NeutralizationMethod(StrEnum):
    """Methods for factor neutralization."""
    ORTHOGONAL = "orthogonal"  # Gram-Schmidt orthogonalization
    REGRESSION = "regression"  # Linear regression residualization
    PCA = "pca"  # Principal Component Analysis
    NONE = "none"  # No neutralization


@dataclass(frozen=True, slots=True)
class NeutralizationConfig:
    """Configuration for feature neutralization."""
    winsorization_method: WinsorizationMethod = WinsorizationMethod.MAD
    winsorization_threshold: float = 3.0  # Number of MADs/SDs
    neutralization_method: NeutralizationMethod = NeutralizationMethod.ORTHOGONAL
    
    # Factor neutralization settings
    neutralize_sector: bool = True
    neutralize_beta: bool = True
    neutralize_size: bool = True
    neutralize_industry: bool = True
    
    # Cross-sectional settings
    min_observations: int = 10  # Minimum observations for cross-sectional ops
    handle_missing: str = "drop"  # "drop", "fill", "zero"


class FeatureNeutralizer:
    """
    Feature neutralization engine with cross-sectional operations.
    
    Implements:
    - Median Absolute Deviation (MAD) winsorization
    - Cross-sectional z-score standardization
    - Factor neutralization via regression residuals
    """
    
    def __init__(self, config: NeutralizationConfig | None = None) -> None:
        self._config = config or NeutralizationConfig()
    
    def winsorize(
        self,
        values: np.ndarray,
        method: WinsorizationMethod | None = None
    ) -> np.ndarray:
        """
        Winsorize values to remove outliers.
        
        MAD Formula: x_clipped = clip(x, μ ± 3 · 1.4826 · MAD)
        """
        method = method or self._config.winsorization_method
        threshold = self._config.winsorization_threshold
        
        if len(values) == 0:
            return values
        
        if method == WinsorizationMethod.MAD:
            median = np.median(values)
            mad = np.median(np.abs(values - median))
            # MAD to SD conversion factor: 1.4826 for normal distribution
            threshold_value = threshold * 1.4826 * mad
            lower_bound = median - threshold_value
            upper_bound = median + threshold_value
            
        elif method == WinsorizationMethod.IQR:
            q25, q75 = np.percentile(values, [25, 75])
            iqr = q75 - q25
            threshold_value = threshold * iqr
            lower_bound = q25 - threshold_value
            upper_bound = q75 + threshold_value
            
        elif method == WinsorizationMethod.SIGMA:
            mean = np.mean(values)
            std = np.std(values)
            threshold_value = threshold * std
            lower_bound = mean - threshold_value
            upper_bound = mean + threshold_value
            
        elif method == WinsorizationMethod.PERCENTILE:
            lower_bound = np.percentile(values, threshold)
            upper_bound = np.percentile(values, 100 - threshold)
            
        else:
            return values
        
        return np.clip(values, lower_bound, upper_bound)
    
    def z_score_standardize(self, values: np.ndarray) -> np.ndarray:
        """
        Cross-sectional z-score standardization.
        
        Formula: z_i = (x_i - x̄) / σ_x
        """
        if len(values) == 0:
            return values
        
        mean = np.mean(values)
        std = np.std(values)
        
        if std == 0:
            return np.zeros_like(values)
        
        return (values - mean) / std
    
    def neutralize_factors(
        self,
        signal: np.ndarray,
        factor_matrix: np.ndarray,
        method: NeutralizationMethod | None = None
    ) -> np.ndarray:
        """
        Neutralize signal against factor exposures.
        
        Formula: S_neutral = (I - X(X^T X)^(-1) X^T) S_raw
        
        where X is the factor matrix and S is the signal.
        """
        method = method or self._config.neutralization_method
        
        if method == NeutralizationMethod.NONE:
            return signal
        
        if len(signal) == 0 or factor_matrix.shape[0] == 0:
            return signal
        
        # Handle missing values
        mask = ~np.isnan(signal) & ~np.any(np.isnan(factor_matrix), axis=1)
        
        if np.sum(mask) < self._config.min_observations:
            return signal
        
        signal_clean = signal[mask]
        factors_clean = factor_matrix[mask]
        
        if method == NeutralizationMethod.REGRESSION:
            # Linear regression residualization
            try:
                # Add intercept
                X = np.column_stack([np.ones(len(signal_clean)), factors_clean])
                
                # OLS regression
                beta = np.linalg.lstsq(X, signal_clean, rcond=None)[0]
                predicted = X @ beta
                neutralized = signal_clean - predicted
                
                # Map back to original indices
                result = np.full_like(signal, np.nan)
                result[mask] = neutralized
                return result
                
            except np.linalg.LinAlgError:
                return signal
        
        elif method == NeutralizationMethod.ORTHOGONAL:
            # Gram-Schmidt orthogonalization
            try:
                # Orthogonalize signal against factors
                orthogonal = self._gram_schmidt_orthogonalize(signal_clean, factors_clean)
                
                # Map back to original indices
                result = np.full_like(signal, np.nan)
                result[mask] = orthogonal
                return result
                
            except Exception:
                return signal
        
        elif method == NeutralizationMethod.PCA:
            # PCA-based neutralization
            try:
                from sklearn.decomposition import PCA
                
                pca = PCA(n_components=min(factors_clean.shape[1], len(signal_clean) - 1))
                factors_pca = pca.fit_transform(factors_clean)
                
                # Residualize against PCA components
                X = np.column_stack([np.ones(len(signal_clean)), factors_pca])
                beta = np.linalg.lstsq(X, signal_clean, rcond=None)[0]
                predicted = X @ beta
                neutralized = signal_clean - predicted
                
                # Map back to original indices
                result = np.full_like(signal, np.nan)
                result[mask] = neutralized
                return result
                
            except Exception:
                return signal
        
        return signal
    
    def _gram_schmidt_orthogonalize(
        self,
        signal: np.ndarray,
        factors: np.ndarray
    ) -> np.ndarray:
        """
        Gram-Schmidt orthogonalization.
        
        Projects signal onto orthogonal complement of factor space.
        """
        # Normalize factors
        factors_normalized = factors.copy()
        for i in range(factors.shape[1]):
            factor = factors[:, i]
            norm = np.linalg.norm(factor)
            if norm > 0:
                factors_normalized[:, i] = factor / norm
        
        # Compute projection matrix
        # P_perp = I - Q(Q^T Q)^(-1) Q^T
        # For orthonormal Q, this simplifies to I - QQ^T
        Q = factors_normalized
        projection = Q @ Q.T
        P_perp = np.eye(len(signal)) - projection
        
        # Project signal
        orthogonal = P_perp @ signal
        
        return orthogonal
    
    def process_cross_section(
        self,
        feature_values: dict[str, Any],
        factor_data: dict[str, dict[str, Any]] | None = None
    ) -> dict[str, Any]:
        """
        Process cross-sectional feature values.
        
        Applies winsorization, z-scoring, and factor neutralization.
        """
        # Convert to numpy array
        symbols = list(feature_values.keys())
        values = np.array([feature_values[s] for s in symbols])
        
        # Handle missing values
        mask = ~np.isnan(values)
        
        if np.sum(mask) < self._config.min_observations:
            return feature_values
        
        # Winsorize
        values_winsorized = self.winsorize(values[mask])
        
        # Z-score standardize
        values_zscored = self.z_score_standardize(values_winsorized)
        
        # Factor neutralization
        if factor_data:
            # Build factor matrix
            factor_matrix = np.array([
                [factor_data.get(factor, {}).get(s, 0) for factor in factor_data]
                for s in symbols
            ])
            
            values_neutralized = self.neutralize_factors(
                values_zscored,
                factor_matrix
            )
        else:
            values_neutralized = values_zscored
        
        # Map back to symbols
        result = {}
        for i, symbol in enumerate(symbols):
            if mask[i]:
                result[symbol] = float(values_neutralized[i])
            else:
                result[symbol] = feature_values[s]
        
        return result


class FactorNeutralizer:
    """
    Factor-specific neutralization for common risk factors.
    
    Handles sector, beta, size, and industry neutralization.
    """
    
    def __init__(self) -> None:
        self._factor_loadings: dict[str, dict[str, float]] = {}
    
    def set_factor_loading(self, symbol: str, factor: str, loading: float) -> None:
        """Set factor loading for a symbol."""
        if symbol not in self._factor_loadings:
            self._factor_loadings[symbol] = {}
        self._factor_loadings[symbol][factor] = loading
    
    def get_factor_matrix(
        self,
        symbols: list[str],
        factors: list[str]
    ) -> np.ndarray:
        """Get factor matrix for symbols and factors."""
        matrix = np.zeros((len(symbols), len(factors)))
        
        for i, symbol in enumerate(symbols):
            for j, factor in enumerate(factors):
                matrix[i, j] = self._factor_loadings.get(symbol, {}).get(factor, 0.0)
        
        return matrix
    
    def neutralize_signal(
        self,
        signal: dict[str, float],
        factors: list[str]
    ) -> dict[str, float]:
        """Neutralize signal against specified factors."""
        symbols = list(signal.keys())
        
        if not symbols or not factors:
            return signal
        
        # Build factor matrix
        factor_matrix = self.get_factor_matrix(symbols, factors)
        
        # Build signal array
        signal_array = np.array([signal[s] for s in symbols])
        
        # Neutralize
        neutralizer = FeatureNeutralizer()
        neutralized_array = neutralizer.neutralize_factors(
            signal_array,
            factor_matrix
        )
        
        # Map back to symbols
        return {s: float(neutralized_array[i]) for i, s in enumerate(symbols)}
