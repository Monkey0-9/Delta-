"""Bayesian state estimation with conjugate priors."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional
import numpy as np


@dataclass(frozen=True, slots=True)
class BayesianStateParameters:
    """Parameters for Bayesian state estimator."""
    n_states: int = 3
    prior_counts: float = 1.0  # Dirichlet pseudo-count per state
    confidence: float = 0.95


class BayesianStateEstimator:
    """Categorical-Dirichlet Bayesian estimator over discrete states.

    Tracks Dirichlet posterior counts; exposes posterior mean,
    MAP, and marginal credible intervals via Beta quantiles.
    """

    def __init__(self, params: Optional[BayesianStateParameters] = None) -> None:
        self._params = params or BayesianStateParameters()
        self._counts: np.ndarray = np.full(
            self._params.n_states, float(self._params.prior_counts)
        )

    @property
    def counts(self) -> np.ndarray:
        """Posterior Dirichlet counts."""
        return self._counts.copy()

    @property
    def posterior_mean(self) -> np.ndarray:
        """Posterior mean state probabilities."""
        return self._counts / self._counts.sum()

    def update(
        self,
        state: Optional[int] = None,
        proba: Optional[np.ndarray] = None,
        weight: float = 1.0,
    ) -> np.ndarray:
        """Update posterior with a hard label or soft distribution.

        Args:
            state: Observed discrete state index.
            proba: Soft state distribution (alternative to state).
            weight: Observation weight.

        Returns:
            Updated posterior mean.
        """
        if state is not None:
            if not 0 <= state < self._params.n_states:
                raise ValueError(f"state {state} out of range.")
            self._counts[state] += weight
        elif proba is not None:
            p = np.asarray(proba, dtype=float)
            if p.shape != (self._params.n_states,):
                raise ValueError("proba must match n_states.")
            p = np.clip(p, 0.0, None)
            p = p / max(p.sum(), 1e-12)
            self._counts = self._counts + weight * p
        else:
            raise ValueError("Provide either state or proba.")
        return self.posterior_mean

    def credible_interval(self, state: int) -> tuple[float, float]:
        """Marginal credible interval for one state's probability.

        Uses the Beta marginal of the Dirichlet posterior.
        """
        from scipy.stats import beta

        if not 0 <= state < self._params.n_states:
            raise ValueError(f"state {state} out of range.")
        a = self._counts[state]
        b = self._counts.sum() - a
        alpha = 1.0 - float(self._params.confidence)
        return (float(beta.ppf(alpha / 2, a, b)), float(beta.ppf(1 - alpha / 2, a, b)))

    def reset(self) -> None:
        """Reset posterior to prior."""
        self._counts = np.full(
            self._params.n_states, float(self._params.prior_counts)
        )


__all__ = ["BayesianStateParameters", "BayesianStateEstimator"]
