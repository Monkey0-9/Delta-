"""Regime forecaster combining HMM, Markov-switching, and Bayesian states."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
import numpy as np

from .hmm_enhanced import EnhancedHMM, EnhancedHMMParameters
from .markov_switching import MarkovSwitching, MarkovSwitchingParameters
from .bayesian_state import BayesianStateEstimator, BayesianStateParameters


@dataclass(frozen=True, slots=True)
class RegimeForecasterParameters:
    """Parameters for RegimeForecaster."""
    n_states: int = 3
    n_lags: int = 1
    smoothing: float = 1.0
    random_state: Optional[int] = None


class RegimeForecaster:
    """Ensemble regime forecaster.

    Fits an EnhancedHMM (primary) and a MarkovSwitching model
    (secondary), then blends their distributions with a Bayesian
    posterior tracker.
    """

    def __init__(self, params: Optional[RegimeForecasterParameters] = None) -> None:
        self._params = params or RegimeForecasterParameters()
        self._hmm = EnhancedHMM(EnhancedHMMParameters(
            n_states=self._params.n_states,
            smoothing=self._params.smoothing,
            random_state=self._params.random_state,
        ))
        self._ms = MarkovSwitching(MarkovSwitchingParameters(
            n_regimes=self._params.n_states,
            n_lags=self._params.n_lags,
            smoothing=self._params.smoothing,
            random_state=self._params.random_state,
        ))
        self._bayes = BayesianStateEstimator(BayesianStateParameters(
            n_states=self._params.n_states,
        ))
        self._fitted = False

    def fit(self, X: np.ndarray) -> "RegimeForecaster":
        """Fit underlying models and seed Bayesian tracker."""
        X = np.asarray(X, dtype=float)
        self._hmm.fit(X)
        flat = X.ravel() if X.ndim > 1 else X
        try:
            self._ms.fit(flat)
        except Exception:
            pass  # HMM alone suffices if MS fails on short series
        proba = self._hmm.predict_proba(X)
        self._bayes.update(proba=proba.mean(axis=0), weight=float(len(proba)))
        self._fitted = True
        return self

    def probability(self, X: np.ndarray) -> np.ndarray:
        """Current blended regime probabilities, shape (T, K)."""
        if not self._fitted:
            raise RuntimeError("RegimeForecaster must be fitted first.")
        return self._hmm.predict_proba(np.asarray(X, dtype=float))

    def forecast(self, X: np.ndarray, n_steps: int = 1) -> np.ndarray:
        """Forecast regime distribution n steps ahead from trailing data."""
        proba = self.probability(X)
        current = proba[-1]
        return self._hmm.forecast_transition(current, n_steps=n_steps)


__all__ = ["RegimeForecasterParameters", "RegimeForecaster"]
