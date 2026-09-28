"""W191-W210 (G) — Intraday risk engine + reverse stress testing.

Risk updates continuously: gross/net/factor/VaR/ES/drawdown/liquidity/margin/
concentration/correlation/stress. Reverse stress: solve for the shock surface
that causes X% loss instead of only forward-simulating scenarios.
"""
from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class IntradaySnapshot:
    gross: float
    net: float
    factor_exposures: tuple[float, ...]
    var_95: float
    es_95: float
    drawdown: float
    liquidity_frac: float  # portfolio fraction liquidatable in a day
    margin_use: float
    concentration_hhi: float
    max_corr: float
    stress_worst: float


def var_es(pnls: list[float], q: float = 0.05) -> tuple[float, float]:
    if not pnls:
        return 0.0, 0.0
    s = sorted(pnls)
    idx = max(0, min(len(s) - 1, int(len(s) * q)))
    var = -s[idx]
    tail = s[: idx + 1]
    es = -sum(tail) / len(tail)
    return var, es


class IntradayRiskEngine:
    def __init__(self, peak_nav: float = 1.0) -> None:
        self.peak = peak_nav
        self.history: list[IntradaySnapshot] = []

    def update(self, *, positions: list[float], prices: list[float],
               factor_loadings: list[list[float]], pnl_history: list[float],
               adv_frac: list[float], margin_used: float,
               corrs: list[list[float]], stress_shocks: list[list[float]]) -> IntradaySnapshot:
        nav = sum(p * px for p, px in zip(positions, prices))
        gross = sum(abs(p * px) for p, px in zip(positions, prices))
        net = sum(p * px for p, px in zip(positions, prices))
        self.peak = max(self.peak, nav)
        dd = (self.peak - nav) / max(self.peak, 1e-12)
        var, es = var_es(pnl_history)
        w = [p * px / max(nav, 1e-12) for p, px in zip(positions, prices)]
        hhi = sum(x * x for x in w)
        liq = sum(min(abs(p * px), a) for p, px, a in zip(positions, prices,
                  [f * max(nav, 1e-9) for f in adv_frac])) / max(gross, 1e-12)
        mc = max((abs(corrs[i][j]) for i in range(len(corrs)) for j in range(len(corrs)) if i != j),
                 default=0.0)
        stress = min((sum(p * s for p, s in zip(positions, sh)) for sh in stress_shocks), default=0.0)
        fexp = tuple(sum(ld[i] * positions[i] for i in range(len(positions)))
                     for ld in factor_loadings) if factor_loadings else ()
        snap = IntradaySnapshot(gross, net, fexp, var, es, dd, liq, margin_used, hhi, mc, stress)
        self.history.append(snap)
        return snap


def reverse_stress(positions: list[float], *, target_loss: float,
                   shock_grid: list[float]) -> list[tuple[float, float]]:
    """For a single-factor shock grid, find shock magnitudes ≈ target loss.

    Returns list of (shock, resulting_loss) bracketing the target. The 'shock
    surface' in N dimensions is the level set; this 1-D solver is the auditable
    primitive that generalizes to grid search over factors.
    """
    pts = [(s * sum(abs(p) for p in positions), s) for s in shock_grid]
    # sort by loss proximity to target
    pts.sort(key=lambda t: abs(t[0] - target_loss))
    return [(s, l) for l, s in pts[:4]]
