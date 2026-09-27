"""Orthogonalization Engine for Alpha Signals.

W98: Ensures zero redundancy between candidate alphas by projecting
onto orthogonal complement of existing production alpha subspace.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any
import numpy as np
from scipy.linalg import qr, svd


class OrthogonalizationMethod(StrEnum):
    """Methods for signal orthogonalization."""
    GRAM_SCHMIDT = "gram_schmidt"
    QR_DECOMPOSITION = "qr"
    SVD = "svd"
    PCA = "pca"


@dataclass(frozen=True, slots=True)
class OrthogonalizationConfig:
    """Configuration for orthogonalization."""
    method: OrthogonalizationMethod = OrthogonalizationMethod.QR_DECOMPOSITION
    correlation_threshold: float = 0.30  # Reject if correlation > threshold
    min_variance_explained: float = 0.95  # For PCA/SVD
    normalize_signals: bool = True


class OrthogonalizationEngine:
    """
    Orthogonalization engine for ensuring signal independence.
    
    Projects new candidate alpha vectors onto orthogonal complement
    of existing production alpha subspace via Gram-Schmidt/QR/SVD.
    
    Formula:
        P_perp = I - QQ^T, where span(Q) = span([B | A])
        alpha_orthogonal = P_perp * alpha_new / ||P_perp * alpha_new||
    
    Signals with ||P_perp * alpha_new|| < 0.20 are rejected as disguised
    variants of existing factors.
    """
    
    def __init__(self, config: OrthogonalizationConfig | None = None) -> None:
        self._config = config or OrthogonalizationConfig()
        self._production_alphas: dict[str, np.ndarray] = {}
        self._risk_factors: dict[str, np.ndarray] = {}
    
    def add_production_alpha(self, name: str, signal: np.ndarray) -> None:
        """Add a production alpha to the orthogonal basis."""
        if self._config.normalize_signals:
            signal = self._normalize_vector(signal)
        
        self._production_alphas[name] = signal
    
    def add_risk_factor(self, name: str, factor: np.ndarray) -> None:
        """Add a risk factor to the orthogonal basis."""
        if self._config.normalize_signals:
            factor = self._normalize_vector(factor)
        
        self._risk_factors[name] = factor
    
    def _normalize_vector(self, vector: np.ndarray) -> np.ndarray:
        """Normalize vector to unit length."""
        norm = np.linalg.norm(vector)
        if norm == 0:
            return vector
        return vector / norm
    
    def _build_orthogonal_basis(self) -> np.ndarray:
        """
        Build orthogonal basis from production alphas and risk factors.
        
        Returns matrix Q where columns form orthonormal basis.
        """
        all_signals = []
        
        # Add risk factors
        for factor in self._risk_factors.values():
            all_signals.append(factor)
        
        # Add production alphas
        for alpha in self._production_alphas.values():
            all_signals.append(alpha)
        
        if not all_signals:
            return np.array([]).reshape(0, 0)
        
        # Stack signals
        signal_matrix = np.column_stack(all_signals)
        
        # Perform QR decomposition to get orthonormal basis
        Q, R = qr(signal_matrix, mode='economic')
        
        # Remove columns with zero diagonal in R (linearly dependent)
        rank = np.sum(np.abs(np.diag(R)) > 1e-10)
        Q = Q[:, :rank]
        
        return Q
    
    def orthogonalize_signal(
        self,
        new_signal: np.ndarray,
        method: OrthogonalizationMethod | None = None
    ) -> tuple[np.ndarray, float, bool]:
        """
        Orthogonalize new signal against existing basis.
        
        Returns:
            (orthogonal_signal, orthogonal_component_norm, is_accepted)
        
        Signal is rejected if orthogonal component norm < 0.20
        """
        method = method or self._config.method
        
        if self._config.normalize_signals:
            new_signal = self._normalize_vector(new_signal)
        
        # Build orthogonal basis
        Q = self._build_orthogonal_basis()
        
        if Q.shape[1] == 0:
            # No existing signals, return as-is
            return new_signal, 1.0, True
        
        if method == OrthogonalizationMethod.GRAM_SCHMIDT:
            orthogonal = self._gram_schmidt_orthogonalize(new_signal, Q)
        elif method == OrthogonalizationMethod.QR_DECOMPOSITION:
            orthogonal = self._qr_orthogonalize(new_signal, Q)
        elif method == OrthogonalizationMethod.SVD:
            orthogonal = self._svd_orthogonalize(new_signal, Q)
        elif method == OrthogonalizationMethod.PCA:
            orthogonal = self._pca_orthogonalize(new_signal, Q)
        else:
            orthogonal = self._qr_orthogonalize(new_signal, Q)
        
        # Calculate orthogonal component norm
        orthogonal_norm = np.linalg.norm(orthogonal)
        
        # Check if signal is rejected
        is_accepted = orthogonal_norm >= 0.20
        
        # Normalize if accepted
        if is_accepted and orthogonal_norm > 0:
            orthogonal = orthogonal / orthogonal_norm
        
        return orthogonal, orthogonal_norm, is_accepted
    
    def _gram_schmidt_orthogonalize(
        self,
        signal: np.ndarray,
        basis: np.ndarray
    ) -> np.ndarray:
        """Gram-Schmidt orthogonalization."""
        orthogonal = signal.copy()
        
        for i in range(basis.shape[1]):
            basis_vector = basis[:, i]
            projection = np.dot(orthogonal, basis_vector) * basis_vector
            orthogonal = orthogonal - projection
        
        return orthogonal
    
    def _qr_orthogonalize(
        self,
        signal: np.ndarray,
        basis: np.ndarray
    ) -> np.ndarray:
        """QR-based orthogonalization."""
        # Compute projection matrix: P = Q(Q^T Q)^(-1) Q^T
        # For orthonormal Q, P = QQ^T
        P = basis @ basis.T
        
        # Project signal
        projected = P @ signal
        
        # Get orthogonal component
        orthogonal = signal - projected
        
        return orthogonal
    
    def _svd_orthogonalize(
        self,
        signal: np.ndarray,
        basis: np.ndarray
    ) -> np.ndarray:
        """SVD-based orthogonalization."""
        # Stack signal with basis
        combined = np.column_stack([basis, signal])
        
        # Perform SVD
        U, s, Vt = svd(combined, full_matrices=False)
        
        # The last column of V corresponds to signal component
        # orthogonal to the basis
        signal_projection = Vt[-1, -1]
        
        # Reconstruct orthogonal component
        orthogonal = signal_projection * (U @ np.diag(s) @ Vt)[:, -1]
        
        return orthogonal
    
    def _pca_orthogonalize(
        self,
        signal: np.ndarray,
        basis: np.ndarray
    ) -> np.ndarray:
        """PCA-based orthogonalization."""
        from sklearn.decomposition import PCA
        
        # Stack signal with basis
        combined = np.column_stack([basis, signal])
        
        # Perform PCA
        pca = PCA(n_components=min(combined.shape[1], combined.shape[0] - 1))
        transformed = pca.fit_transform(combined)
        
        # The last component should capture signal variance
        # orthogonal to the principal components of the basis
        orthogonal = transformed[:, -1]
        
        return orthogonal
    
    def check_correlation(
        self,
        signal: np.ndarray,
        existing_signals: dict[str, np.ndarray] | None = None
    ) -> dict[str, float]:
        """
        Check correlation of signal with existing signals.
        
        Returns dict mapping signal name to correlation coefficient.
        """
        if existing_signals is None:
            existing_signals = self._production_alphas
        
        correlations = {}
        
        for name, existing_signal in existing_signals.items():
            # Ensure same length
            min_len = min(len(signal), len(existing_signal))
            signal_trimmed = signal[:min_len]
            existing_trimmed = existing_signal[:min_len]
            
            # Calculate correlation
            if np.std(signal_trimmed) > 0 and np.std(existing_trimmed) > 0:
                corr = np.corrcoef(signal_trimmed, existing_trimmed)[0, 1]
                correlations[name] = corr if not np.isnan(corr) else 0.0
            else:
                correlations[name] = 0.0
        
        return correlations
    
    def validate_signal_orthogonality(
        self,
        signal: np.ndarray
    ) -> dict[str, Any]:
        """
        Validate signal orthogonality against production alphas.
        
        Returns validation report with acceptance decision.
        """
        # Orthogonalize signal
        orthogonal, norm, is_accepted = self.orthogonalize_signal(signal)
        
        # Check correlations
        correlations = self.check_correlation(signal)
        
        # Find max correlation
        max_corr = max(correlations.values()) if correlations else 0.0
        
        # Final decision
        final_accepted = (
            is_accepted
            and max_corr < self._config.correlation_threshold
        )
        
        return {
            "is_accepted": final_accepted,
            "orthogonal_norm": norm,
            "max_correlation": max_corr,
            "correlations": correlations,
            "rejection_reason": self._get_rejection_reason(is_accepted, max_corr),
        }
    
    def _get_rejection_reason(self, is_accepted: bool, max_corr: float) -> str | None:
        """Get rejection reason if signal is rejected."""
        if is_accepted and max_corr < self._config.correlation_threshold:
            return None
        
        if not is_accepted:
            return f"Orthogonal component norm {is_accepted} < 0.20 threshold"
        
        if max_corr >= self._config.correlation_threshold:
            return f"Max correlation {max_corr:.3f} >= {self._config.correlation_threshold} threshold"
        
        return "Unknown rejection reason"
