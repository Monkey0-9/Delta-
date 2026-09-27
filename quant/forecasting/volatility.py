"""Volatility models: arch GARCH(1,1) fit + HMM regime states (hmmlearn).

Deterministic: fixed random_state, no random restarts. HMM states are ordered
by fitted variance and mapped onto the canonical Regime vocabulary.
"""
from __future__ import annotations

import numpy as np

from quant.regime.regime import Regime


def garch_forecast_variance(returns: np.ndarray, horizon: int = 5) -> np.ndarray:
    """GARCH(1,1) h-step conditional variance forecast via `arch`."""
    from arch import arch_model

    r = np.asarray(returns, dtype=np.float64)
    if r.ndim != 1 or len(r) < 50:
        raise ValueError("need >= 50 returns for GARCH.")
    if not np.isfinite(r).all():
        raise ValueError("non-finite values rejected.")
    if horizon < 1:
        raise ValueError("horizon must be >= 1.")
    fit = arch_model(r * 100.0, vol="Garch", p=1, q=1).fit(disp="off")
    var = np.asarray(fit.forecast(horizon=horizon).variance.values[-1, :], dtype=np.float64)
    return var / 10000.0


def hmm_regime_states(returns: np.ndarray, n_states: int = 3) -> tuple[Regime, ...]:
    """Gaussian HMM on returns; states ranked by variance -> Regime labels.

    Lowest-variance state -> NORMAL, middle -> HIGH_VOLATILITY (or TRENDING
    when its mean dominates), highest -> CRISIS.
    """
    from hmmlearn.hmm import GaussianHMM

    r = np.asarray(returns, dtype=np.float64).reshape(-1, 1)
    if len(r) < 30 or n_states < 2:
        raise ValueError("need >= 30 returns and >= 2 states.")
    if not np.isfinite(r).all():
        raise ValueError("non-finite values rejected.")
    model = GaussianHMM(n_components=n_states, covariance_type="full",
                        n_iter=100, random_state=0)
    model.fit(r)
    states = model.predict(r)
    order = sorted(range(n_states), key=lambda s: float(model.covars_[s].ravel()[0]))
    labels: dict[int, Regime] = {}
    labels[order[0]] = Regime.NORMAL
    labels[order[-1]] = Regime.CRISIS
    for s in order[1:-1]:
        mean = float(model.means_[s].ravel()[0])
        vol = float(model.covars_[s].ravel()[0]) ** 0.5
        labels[s] = Regime.TRENDING if abs(mean) > vol else Regime.HIGH_VOLATILITY
    return tuple(labels[int(s)] for s in states)
