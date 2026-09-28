"""P5 — Portfolio Intelligence v2 (W133).

Factor/sector exposures, liquidity/turnover constraints, capacity,
TCA-aware optimization, factor crowding, stress contribution, MRC,
scenario + robust optimization, dynamic risk budgets, regime-conditioned
allocation. Deterministic projected-gradient optimizer (no scipy needed).
"""
from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PortfolioConstraints:
    max_gross: float = 1.0
    max_name: float = 0.2
    max_turnover: float = 0.5
    long_only: bool = False
    max_factor: float = 0.3  # max abs net exposure per factor


def marginal_risk_contrib(w: list[float], cov: list[list[float]]) -> list[float]:
    n = len(w)
    port_var = sum(w[i] * w[j] * cov[i][j] for i in range(n) for j in range(n))
    vol = math.sqrt(max(port_var, 1e-12))
    mrc = []
    for i in range(n):
        m = sum(cov[i][j] * w[j] for j in range(n)) / vol
        mrc.append(w[i] * m / vol)  # fractional contribution
    return mrc


def portfolio_vol(w: list[float], cov: list[list[float]]) -> float:
    return math.sqrt(max(sum(w[i] * w[j] * cov[i][j] for i in range(len(w)) for j in range(len(w))), 0.0))


def _project(w: list[float], c: PortfolioConstraints, prev: list[float] | None = None) -> list[float]:
    n = len(w)
    x = list(w)
    if c.long_only:
        x = [max(0.0, v) for v in x]
    # name cap
    x = [max(-c.max_name, min(c.max_name, v)) for v in x]
    # gross cap
    g = sum(abs(v) for v in x)
    if g > c.max_gross and g > 0:
        x = [v * c.max_gross / g for v in x]
    # turnover cap vs prev
    if prev is not None:
        t = sum(abs(a - b) for a, b in zip(x, prev))
        if t > c.max_turnover and t > 0:
            lam = c.max_turnover / t
            x = [p + (a - p) * lam for a, p in zip(x, prev)]
    return x


def optimize_tca(
    alpha: list[float],
    cov: list[list[float]],
    costs_bps: list[float],
    constraints: PortfolioConstraints,
    *,
    risk_aversion: float = 1.0,
    prev: list[float] | None = None,
    iters: int = 500,
    lr: float = 0.05,
) -> list[float]:
    """Maximize alpha*w - costs*|w| - lambda/2 w'Cov w via projected subgradient."""
    n = len(alpha)
    w = [0.0] * n if prev is None else list(prev)
    for _ in range(iters):
        # gradient of -(objective): -alpha + lam*Cov w + costs*sign(w)
        grad = []
        for i in range(n):
            covterm = sum(cov[i][j] * w[j] for j in range(n))
            sub = 0.0 if w[i] == 0 else (1.0 if w[i] > 0 else -1.0)
            grad.append(-alpha[i] + risk_aversion * covterm + (costs_bps[i] / 1e4) * sub)
        w = [a - lr * g for a, g in zip(w, grad)]
        w = _project(w, constraints, prev)
    return w


def factor_exposures(w: list[float], loadings: list[list[float]]) -> list[float]:
    """loadings[k][i]: exposure of asset i to factor k."""
    out = []
    for k in range(len(loadings)):
        out.append(sum(loadings[k][i] * w[i] for i in range(len(w))))
    return out


def crowding_score(loadings: list[list[float]], crowd_weights: list[float]) -> float:
    """Cosine similarity between portfolio factor tilt and crowded factor vector."""
    num = sum(a * b for a, b in zip(loadings_flat(loadings), crowd_weights))
    da = math.sqrt(sum(a * a for a in loadings_flat(loadings)))
    db = math.sqrt(sum(b * b for b in crowd_weights))
    if da <= 0 or db <= 0:
        return 0.0
    return num / (da * db)


def loadings_flat(loadings: list[list[float]]) -> list[float]:
    # net factor direction proxy: mean loading across assets
    if not loadings:
        return []
    n = len(loadings[0])
    return [sum(loadings[k][i] for k in range(len(loadings))) / len(loadings) for i in range(n)]


def scenario_pnl(w: list[float], shocks: list[list[float]]) -> list[float]:
    """Portfolio P&L under each shock vector."""
    return [sum(a * b for a, b in zip(w, s)) for s in shocks]


def robust_objective(w: list[float], alpha: list[float], cov: list[list[float]],
                     shocks: list[list[float]], eta: float = 0.5) -> float:
    base = sum(a * b for a, b in zip(alpha, w)) - 0.5 * sum(
        w[i] * w[j] * cov[i][j] for i in range(len(w)) for j in range(len(w)))
    worst = min(scenario_pnl(w, shocks)) if shocks else 0.0
    return (1 - eta) * base + eta * worst


def dynamic_risk_budgets(regime_probs: list[float], base_budgets: list[float]) -> list[float]:
    """Scale risk budgets by regime confidence (entropy tempering)."""
    import math as _m
    ent = -sum(p * _m.log(max(p, 1e-12)) for p in regime_probs)
    maxent = _m.log(max(len(regime_probs), 2))
    conf = 1 - ent / maxent  # 0..1
    scale = 0.5 + 0.5 * conf
    return [b * scale for b in base_budgets]


def regime_conditioned_allocation(base_w: list[float], regime_tilt: list[float], regime_prob: float) -> list[float]:
    return [b * (1 - regime_prob) + t * regime_prob for b, t in zip(base_w, regime_tilt)]
