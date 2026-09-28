"""P4 — Probabilistic World Model (W132).

Observed data -> latent state -> HMM/Markov-switching -> Kalman/state-space ->
Bayesian state estimation -> transition probability -> future regime
distribution -> regime-conditional alpha -> portfolio decision.

Regime classification != world model: this module represents UNCERTAINTY
over latent state and its evolution (full predictive distribution).
Deterministic given seed; pure python (no sklearn/hmmlearn dependency).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field


def _xorshift(state: int) -> int:
    x = state & 0xFFFFFFFF or 1
    x ^= (x << 13) & 0xFFFFFFFF
    x ^= x >> 17
    x ^= (x << 5) & 0xFFFFFFFF
    return x


@dataclass
class MarkovSwitchingModel:
    """Discrete latent regime with Gaussian emissions; Baum-Welch (few iters, deterministic)."""

    n_states: int = 3
    seed: int = 7
    trans: list[list[float]] = field(default_factory=list)
    means: list[float] = field(default_factory=list)
    vols: list[float] = field(default_factory=list)

    def fit(self, x: list[float], iters: int = 12) -> "MarkovSwitchingModel":
        k = self.n_states
        n = len(x)
        if n < k + 1:
            raise ValueError("not enough observations")
        rng = self.seed & 0xFFFFFFFF or 1
        # init: quantile means, uniform transitions
        xs = sorted(x)
        self.means = [xs[int((i + 0.5) * n / k)] for i in range(k)]
        m = sum(x) / n
        v = sum((v - m) ** 2 for v in x) / n or 1.0
        self.vols = [math.sqrt(v)] * k
        self.trans = [[(0.8 if i == j else 0.2 / (k - 1)) for j in range(k)] for i in range(k)]
        for _ in range(iters):
            # E-step: forward-backward
            loge = [[self._logN(v, self.means[s], self.vols[s]) for s in range(k)] for v in x]
            alpha = [[loge[0][s] + math.log(1.0 / k) for s in range(k)]]
            for t in range(1, n):
                row = []
                for s in range(k):
                    best = max(alpha[t - 1][p] + math.log(max(self.trans[p][s], 1e-12)) for p in range(k))
                    # log-sum-exp
                    acc = sum(math.exp(alpha[t - 1][p] + math.log(max(self.trans[p][s], 1e-12)) - best) for p in range(k))
                    row.append(loge[t][s] + best + math.log(acc))
                alpha.append(row)
            beta = [[0.0] * k]
            for t in range(n - 2, -1, -1):
                row = []
                for s in range(k):
                    acc = sum(math.exp(math.log(max(self.trans[s][q], 1e-12)) + loge[t + 1][q] + beta[0][q]) for q in range(k))
                    row.append(math.log(max(acc, 1e-300)))
                beta.insert(0, row)
            gamma = []
            for t in range(n):
                un = [math.exp(alpha[t][s] + beta[t][s]) for s in range(k)]
                tot = sum(un) or 1.0
                gamma.append([u / tot for u in un])
            # M-step
            for s in range(k):
                w = sum(gamma[t][s] for t in range(n))
                if w < 1e-9:
                    continue
                self.means[s] = sum(gamma[t][s] * x[t] for t in range(n)) / w
                var = sum(gamma[t][s] * (x[t] - self.means[s]) ** 2 for t in range(n)) / w
                self.vols[s] = math.sqrt(max(var, 1e-8))
            for i in range(k):
                for j in range(k):
                    num = den = 0.0
                    for t in range(n - 1):
                        # joint approx gamma[t][i]*T[i][j]*e / norm (simplified re-estimate)
                        num += gamma[t][i] * gamma[t + 1][j]
                        den += gamma[t][i]
                    self.trans[i][j] = num / max(den, 1e-12)
                tot = sum(self.trans[i]) or 1.0
                self.trans[i] = [v / tot for v in self.trans[i]]
        return self

    @staticmethod
    def _logN(v: float, mu: float, sig: float) -> float:
        return -0.5 * math.log(2 * math.pi * max(sig, 1e-8) ** 2) - (v - mu) ** 2 / (2 * max(sig, 1e-8) ** 2)

    def filter(self, x: list[float]) -> list[list[float]]:
        """Forward filtered state probabilities p(s_t | x_1..t)."""
        k = self.n_states
        probs: list[list[float]] = []
        prev = [1.0 / k] * k
        for v in x:
            like = [math.exp(self._logN(v, self.means[s], self.vols[s])) for s in range(k)]
            pred = [sum(prev[p] * self.trans[p][s] for p in range(k)) for s in range(k)]
            un = [pred[s] * like[s] for s in range(k)]
            tot = sum(un) or 1.0
            post = [u / tot for u in un]
            probs.append(post)
            prev = post
        return probs

    def predictive_distribution(self, belief: list[float], horizon: int) -> list[list[float]]:
        """Evolve belief h steps: full future regime distribution."""
        out = []
        b = list(belief)
        for _ in range(horizon):
            b = [sum(b[p] * self.trans[p][s] for p in range(len(b))) for s in range(len(b))]
            out.append(list(b))
        return out

    def stationary(self) -> list[float]:
        k = self.n_states
        # power iteration
        b = [1.0 / k] * k
        for _ in range(200):
            b = [sum(b[p] * self.trans[p][s] for p in range(k)) for s in range(k)]
        return b


@dataclass
class Kalman1D:
    """Scalar Kalman filter for latent level; exposes uncertainty (P)."""

    q: float = 1e-4
    r: float = 1e-2
    x: float = 0.0
    p: float = 1.0

    def step(self, z: float) -> tuple[float, float]:
        # predict
        pp = self.p + self.q
        # update
        k = pp / (pp + self.r)
        self.x = self.x + k * (z - self.x)
        self.p = (1 - k) * pp
        return self.x, self.p

    def run(self, series: list[float]) -> list[tuple[float, float]]:
        return [self.step(z) for z in series]


@dataclass(frozen=True, slots=True)
class RegimeConditionalAlpha:
    regime: int
    alpha_mean: float
    alpha_vol: float
    weight: float  # posterior weight of regime


def _pos(s: list[float]) -> list[float]:
    return [max(0.0, v) for v in s]


def regime_conditional_weights(
    pred_dist: list[float], regime_sharpes: list[float], risk_aversion: float = 1.0
) -> list[float]:
    """Posterior-weighted regime allocation (uncertainty-aware, sums to 1 if positive)."""
    scores = [max(s, 0.0) * p for s, p in zip(_pos(regime_sharpes), pred_dist)]
    tot = sum(scores)
    if tot <= 0:
        k = len(pred_dist)
        return [1.0 / k] * k
    return [s / tot for s in scores]
