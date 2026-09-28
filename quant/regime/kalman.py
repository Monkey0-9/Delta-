"""W101-W110: Kalman filter + Markov transition forecasting for latent market state.

Complements quant/regime/hmm.py (discrete Baum-Welch). This module adds:
- 1D Kalman filter for latent level/trend (state-space / dynamic Bayesian estimation)
- Transition matrix estimation from Viterbi state sequences
- N-step transition probability forecasting + persistence + uncertainty
- Regime-conditioned alpha weighting helper
"""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np

STATE_VERSION = "regime-state-v1"


@dataclass
class KalmanState:
    level: float
    variance: float


class KalmanFilter1D:
    """Scalar Kalman filter: x_t = x_{t-1} + w, y_t = x_t + v."""

    def __init__(self, process_var: float = 1e-4, obs_var: float = 1e-2,
                 init_level: float = 0.0, init_var: float = 1.0) -> None:
        if process_var <= 0 or obs_var <= 0 or init_var <= 0:
            raise ValueError("variances must be positive.")
        self.q = process_var
        self.r = obs_var
        self.state = KalmanState(init_level, init_var)

    def update(self, obs: float) -> KalmanState:
        if not np.isfinite(obs):
            raise ValueError("observation must be finite.")
        # predict
        pred_var = self.state.variance + self.q
        # update
        gain = pred_var / (pred_var + self.r)
        level = self.state.level + gain * (obs - self.state.level)
        var = (1.0 - gain) * pred_var
        self.state = KalmanState(level, var)
        return self.state

    def filter_series(self, obs: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        levels = np.zeros(len(obs))
        variances = np.zeros(len(obs))
        for i, y in enumerate(obs):
            s = self.update(float(y))
            levels[i] = s.level
            variances[i] = s.variance
        return levels, variances


def estimate_transition_matrix(states: np.ndarray, n_states: int,
                               smoothing: float = 1e-6) -> np.ndarray:
    """Maximum-likelihood P(j|i) with Laplace smoothing; rows sum to 1."""
    if len(states) < 2:
        raise ValueError("need at least 2 states to estimate transitions.")
    counts = np.full((n_states, n_states), smoothing)
    for a, b in zip(states[:-1], states[1:]):
        counts[int(a), int(b)] += 1.0
    return counts / counts.sum(axis=1, keepdims=True)


def forecast_distribution(transition: np.ndarray, current: np.ndarray, steps: int) -> np.ndarray:
    """N-step ahead regime distribution: p_{t+n} = p_t @ T^n."""
    if steps < 1:
        raise ValueError("steps must be >= 1.")
    return current @ np.linalg.matrix_power(transition, steps)


def persistence(transition: np.ndarray) -> np.ndarray:
    """Latent-state persistence = diagonal of T (P(stay))."""
    return np.diag(transition)


def regime_uncertainty(distribution: np.ndarray) -> float:
    """Normalized entropy in [0,1]; 1 = maximum uncertainty."""
    p = np.asarray(distribution, dtype=float)
    p = p / p.sum() if p.sum() > 0 else np.ones_like(p) / len(p)
    entropy = -np.sum(p * np.log(p + 1e-12))
    return float(entropy / np.log(len(p)))


def regime_conditioned_weights(alpha_by_regime: np.ndarray,
                               regime_dist: np.ndarray) -> np.ndarray:
    """Weight alphas by posterior regime distribution (sums to dist-weighted mean)."""
    a = np.asarray(alpha_by_regime, dtype=float)
    p = np.asarray(regime_dist, dtype=float)
    p = p / p.sum()
    if a.shape[0] != p.shape[0]:
        raise ValueError("alpha_by_regime and regime_dist must align on regimes.")
    return a * p
