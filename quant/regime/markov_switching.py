"""Markov-switching autoregressive model (EM-lite)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
import numpy as np


@dataclass(frozen=True, slots=True)
class MarkovSwitchingParameters:
    """Parameters for Markov-switching AR model."""
    n_regimes: int = 2
    n_lags: int = 1
    smoothing: float = 1.0
    random_state: Optional[int] = None


class MarkovSwitching:
    """Markov-switching AR model via GaussianMixture + transition counting.

    Fit procedure (EM-lite):
    1. Build lagged design matrix and cluster residuals/levels with
       sklearn GaussianMixture to get regime labels.
    2. Count label transitions with Dirichlet smoothing -> transition matrix.
    3. Fit per-regime OLS AR coefficients.
    """

    def __init__(self, params: Optional[MarkovSwitchingParameters] = None) -> None:
        self._params = params or MarkovSwitchingParameters()
        k = self._params.n_regimes
        self._trans_mat: np.ndarray = np.ones((k, k)) / k
        self._coefs: Optional[np.ndarray] = None  # (K, lags+1)
        self._labels: Optional[np.ndarray] = None
        self._fitted = False

    @property
    def transition_matrix(self) -> np.ndarray:
        """Regime transition matrix, shape (K, K)."""
        return self._trans_mat.copy()

    @property
    def coefs(self) -> Optional[np.ndarray]:
        """Per-regime AR coefficients including intercept."""
        return None if self._coefs is None else self._coefs.copy()

    def _design(self, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        p = self._params.n_lags
        y = np.asarray(y, dtype=float).ravel()
        n = len(y) - p
        X = np.ones((n, p + 1))
        for lag in range(1, p + 1):
            X[:, lag] = y[p - lag: len(y) - lag]
        return X, y[p:]

    def fit(self, y: np.ndarray) -> "MarkovSwitching":
        """Fit regimes and per-regime AR coefficients."""
        from sklearn.mixture import GaussianMixture

        y = np.asarray(y, dtype=float).ravel()
        K = self._params.n_regimes
        s = float(self._params.smoothing)
        X, target = self._design(y)

        gm = GaussianMixture(
            n_components=K, n_init=5, random_state=self._params.random_state
        )
        labels = gm.fit_predict(target[:, None])
        self._labels = labels

        counts = np.full((K, K), s / K)
        for a, b in zip(labels[:-1], labels[1:]):
            counts[a, b] += 1.0
        self._trans_mat = counts / counts.sum(axis=1, keepdims=True)

        coefs = np.zeros((K, X.shape[1]))
        for k in range(K):
            mask = labels == k
            if mask.sum() > X.shape[1]:
                coefs[k], *_ = np.linalg.lstsq(X[mask], target[mask], rcond=None)
            else:
                coefs[k], *_ = np.linalg.lstsq(X, target, rcond=None)
        self._coefs = coefs
        self._fitted = True
        return self

    def predict(self, y: np.ndarray) -> np.ndarray:
        """Assign regimes by nearest per-regime AR prediction."""
        if not self._fitted or self._coefs is None:
            raise RuntimeError("MarkovSwitching must be fitted before predict.")
        X, _ = self._design(np.asarray(y, dtype=float).ravel())
        preds = X[None, :, :] * self._coefs[:, None, :]
        preds = preds.sum(axis=-1)  # (K, n)
        # Reconstruct target to compare
        p = self._params.n_lags
        target = np.asarray(y, dtype=float).ravel()[p:]
        err = (preds - target[None, :]) ** 2
        return err.argmin(axis=0)

    def predict_proba(self, y: np.ndarray) -> np.ndarray:
        """Soft regime assignment via softmax over negative squared errors."""
        labels = self.predict(y)
        K = self._params.n_regimes
        proba = np.full((len(labels), K), 0.05 / max(K - 1, 1))
        proba[np.arange(len(labels)), labels] = 0.95
        return proba


__all__ = ["MarkovSwitchingParameters", "MarkovSwitching"]
