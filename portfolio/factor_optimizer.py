"""W191-W210 (F) — Factor-aware optimizer with nonlinear portfolio costs.

objective = expected_alpha - risk - transaction_cost - market_impact
            - liquidity_penalty - concentration_penalty
Factors: beta, sector, industry, size, value, momentum, volatility,
liquidity, rates, fx, commodity.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

FACTORS: tuple[str, ...] = ("beta", "sector", "industry", "size", "value", "momentum",
                            "volatility", "liquidity", "rates", "fx", "commodity")


@dataclass
class NonlinearCosts:
    tcost_bps: float = 2.0
    impact_gamma: float = 50.0
    liq_penalty: float = 0.5
    conc_penalty: float = 1.0


def objective(w: list[float], alpha: list[float], cov: list[list[float]],
              adv_frac: list[float], costs: NonlinearCosts,
              risk_aversion: float = 1.0) -> float:
    n = len(w)
    ret = sum(a * x for a, x in zip(alpha, w))
    risk = 0.5 * risk_aversion * sum(w[i] * w[j] * cov[i][j] for i in range(n) for j in range(n))
    tc = sum(abs(x) * costs.tcost_bps / 1e4 for x in w)
    imp = sum(costs.impact_gamma * (abs(x) / max(adv, 1e-9)) ** 1.5 for x, adv in zip(w, adv_frac))
    liq = costs.liq_penalty * sum((abs(x) / max(adv, 1e-9)) ** 2 for x, adv in zip(w, adv_frac))
    conc = costs.conc_penalty * sum(x * x for x in w)
    return ret - risk - tc - imp - liq - conc


def optimize_factor_constrained(
    alpha: list[float], cov: list[list[float]], loadings: dict[str, list[float]],
    factor_caps: dict[str, float], adv_frac: list[float], costs: NonlinearCosts,
    *, risk_aversion: float = 1.0, max_name: float = 0.2, max_gross: float = 1.0,
    iters: int = 400, lr: float = 0.05, seed: int = 7,
) -> list[float]:
    """Projected gradient ascent on the nonlinear objective with factor caps."""
    n = len(alpha)
    w = [0.0] * n
    for _ in range(iters):
        # finite-difference gradient (auditable, dependency-free)
        grad = []
        base = objective(w, alpha, cov, adv_frac, costs, risk_aversion)
        eps = 1e-6
        for i in range(n):
            w[i] += eps
            grad.append((objective(w, alpha, cov, adv_frac, costs, risk_aversion) - base) / eps)
            w[i] -= eps
        w = [x + lr * g for x, g in zip(w, grad)]
        # project: name cap, gross cap
        w = [max(-max_name, min(max_name, x)) for x in w]
        g = sum(abs(x) for x in w)
        if g > max_gross and g > 0:
            w = [x * max_gross / g for x in w]
        # factor caps: scale down proportionally if breached
        for fname, cap in factor_caps.items():
            load = loadings.get(fname)
            if not load:
                continue
            exp = sum(l * x for l, x in zip(load, w))
            if abs(exp) > cap and abs(exp) > 0:
                w = [x * cap / abs(exp) for x in w]
    return w


def factor_exposure(w: list[float], loadings: dict[str, list[float]]) -> dict[str, float]:
    return {f: sum(l * x for l, x in zip(load, w)) for f, load in loadings.items()}
