"""Enhanced Hidden Markov Model with Bayesian state estimation.

Extends :mod:`quant.regime.hmm` with posterior smoothing,
transition forecasting, and uncertainty quantification.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional
import numpy as np
from scipy.special import logsumexp


@dataclass(frozen=True, slots=True)
class EnhancedHMMParameters:
    """Parameters for EnhancedHMM."""
    n_states: int = 3
    n_features: int = 1
    smoothing: float = 1.0  # Dirichlet pseudo-count for transitions
    random_state: Optional[int] = None


@dataclass
class BayesianStatePosterior:
    """Posterior over hidden states at each time step."""
    gamma: np.ndarray  # (T, K) smoothed responsibilities
    entropy: np.ndarray  # (T,) Shannon entropy per step
    credible_mass: np.ndarray  # (T,) max posterior mass per step


class EnhancedHMM:
    """Gaussian-emission HMM with Bayesian transition smoothing.

    Features:
    - EM-lite fitting (k-means init + Gaussian M-step + counted transitions)
    - Forward-backward posterior (Bayesian state estimation)
    - Transition forecasting (n-step ahead distribution)
    - Uncertainty quantification via posterior entropy
    """

    def __init__(self, params: Optional[EnhancedHMMParameters] = None) -> None:
        self._params = params or EnhancedHMMParameters()
        self._rng = np.random.default_rng(self._params.random_state)
        k = self._params.n_states
        self.means_: np.ndarray = np.zeros((k, self._params.n_features))
        self.vars_: np.ndarray = np.ones((k, self._params.n_features))
        self.trans_mat_: np.ndarray = np.ones((k, k)) / k
        self.init_dist_: np.ndarray = np.ones(k) / k
        self._fitted: bool = False

    def _init_states(self, X: np.ndarray) -> np.ndarray:
        """K-means++ lite init via sklearn if available, else random choice."""
        try:
            from sklearn.cluster import KMeans
            km = KMeans(
                n_clusters=self._params.n_states,
                n_init=10,
                random_state=self._params.random_state,
            )
            return km.fit_predict(X)
        except Exception:
            idx = self._rng.choice(
                len(X), size=self._params.n_states, replace=False
            )
            centers = X[idx]
            d = ((X[:, None, :] - centers[None, :, :]) ** 2).sum(-1)
            return d.argmin(axis=1)

    @staticmethod
    def _gauss_logpdf(X: np.ndarray, means: np.ndarray, vars_: np.ndarray) -> np.ndarray:
        """Log emission density, shape (T, K)."""
        vars_safe = np.maximum(vars_, 1e-6)
        diff = X[:, None, :] - means[None, :, :]
        ll = -0.5 * (np.log(2.0 * np.pi * vars_safe)[None, :, :]
                     + diff ** 2 / vars_safe[None, :, :])
        return ll.sum(axis=-1)

    def fit(self, X: np.ndarray, max_iter: int = 50, tol: float = 1e-4) -> "EnhancedHMM":
        """Fit Gaussian HMM via EM.

        Args:
            X: Observations shaped (T,) or (T, F).
            max_iter: Max EM iterations.
            tol: Log-likelihood convergence tolerance.

        Returns:
            Self.
        """
        X = np.asarray(X, dtype=float)
        if X.ndim == 1:
            X = X[:, None]
        T, F = X.shape
        K = self._params.n_states
        s = float(self._params.smoothing)

        labels = self._init_states(X)
        for k in range(K):
            pts = X[labels == k]
            if len(pts) > 1:
                self.means_[k] = pts.mean(axis=0)
                self.vars_[k] = pts.var(axis=0) + 1e-3
            elif len(pts) == 1:
                self.means_[k] = pts[0]
            else:
                self.means_[k] = X.mean(axis=0) + self._rng.normal(scale=0.1, size=F)

        prev_ll = -np.inf
        for _ in range(max_iter):
            log_em = self._gauss_logpdf(X, self.means_, self.vars_)
            log_alpha, ll = self._forward_log(log_em)
            log_beta = self._backward_log(log_em)
            log_gamma = log_alpha + log_beta
            log_gamma -= logsumexp(log_gamma, axis=1, keepdims=True)
            gamma = np.exp(log_gamma)

            # Transition posterior (xi summed) with Dirichlet smoothing
            xi_sum = np.zeros((K, K))
            for t in range(T - 1):
                log_xi = (log_alpha[t][:, None] + np.log(self.trans_mat_ + 1e-12)
                          + log_em[t + 1][None, :] + log_beta[t + 1][None, :])
                log_xi -= logsumexp(log_xi)
                xi_sum += np.exp(log_xi)
            xi_sum += s / K  # Bayesian Dirichlet prior
            self.trans_mat_ = xi_sum / xi_sum.sum(axis=1, keepdims=True)
            self.init_dist_ = gamma[0] / gamma[0].sum()

            # Gaussian M-step
            nk = gamma.sum(axis=0)
            self.means_ = (gamma.T @ X) / np.maximum(nk, 1e-12)[:, None]
            diff = X[:, None, :] - self.means_[None, :, :]
            self.vars_ = ((gamma[:, :, None] * diff ** 2).sum(axis=0)
                          / np.maximum(nk, 1e-12)[:, None])
            self.vars_ = np.maximum(self.vars_, 1e-6)

            if abs(ll - prev_ll) < tol:
                break
            prev_ll = ll
        self._fitted = True
        return self

    def _forward_log(self, log_em: np.ndarray) -> tuple[np.ndarray, float]:
        T, K = log_em.shape
        la = np.zeros((T, K))
        la[0] = np.log(self.init_dist_ + 1e-12) + log_em[0]
        log_A = np.log(self.trans_mat_ + 1e-12)
        for t in range(1, T):
            la[t] = log_em[t] + logsumexp(la[t - 1][:, None] + log_A, axis=0)
        return la, float(logsumexp(la[-1]))

    def _backward_log(self, log_em: np.ndarray) -> np.ndarray:
        T, K = log_em.shape
        lb = np.zeros((T, K))
        log_A = np.log(self.trans_mat_ + 1e-12)
        for t in range(T - 2, -1, -1):
            lb[t] = logsumexp(log_A + log_em[t + 1][None, :] + lb[t + 1][None, :], axis=1)
        return lb

    def posterior(self, X: np.ndarray) -> BayesianStatePosterior:
        """Bayesian smoothed state posterior with uncertainty."""
        X = np.asarray(X, dtype=float)
        if X.ndim == 1:
            X = X[:, None]
        log_em = self._gauss_logpdf(X, self.means_, self.vars_)
        log_alpha, _ = self._forward_log(log_em)
        log_beta = self._backward_log(log_em)
        log_gamma = log_alpha + log_beta
        log_gamma -= logsumexp(log_gamma, axis=1, keepdims=True)
        gamma = np.exp(log_gamma)
        with np.errstate(divide="ignore"):
            ent = -(gamma * np.log(np.maximum(gamma, 1e-12))).sum(axis=1)
        return BayesianStatePosterior(
            gamma=gamma, entropy=ent, credible_mass=gamma.max(axis=1)
        )

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """Posterior state probabilities, shape (T, K)."""
        return self.posterior(X).gamma

    def predict(self, X: np.ndarray) -> np.ndarray:
        """Most likely state per step."""
        return self.predict_proba(X).argmax(axis=1)

    def forecast_transition(self, proba: np.ndarray, n_steps: int = 1) -> np.ndarray:
        """Propagate a state distribution n steps via transition matrix.

        Args:
            proba: State distribution shaped (K,).
            n_steps: Forecast horizon.

        Returns:
            Forecasted distribution shaped (K,).
        """
        p = np.asarray(proba, dtype=float)
        p = p / max(p.sum(), 1e-12)
        A = np.linalg.matrix_power(self.trans_mat_, max(int(n_steps), 1))
        return p @ A

    def uncertainty(self, X: np.ndarray) -> np.ndarray:
        """Per-step posterior entropy (higher = more uncertain)."""
        return self.posterior(X).entropy


__all__ = ["EnhancedHMMParameters", "BayesianStatePosterior", "EnhancedHMM"]
