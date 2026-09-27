"""W97 portfolio construction + institutional risk engine (light but real)."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

OPT_VERSION = "opt-v2"
RISK_VERSION = "risk-v2"


@dataclass(frozen=True, slots=True)
class TargetPortfolio:
    weights: dict[str, float]
    method: str
    expected_return: float
    expected_vol: float


def optimize(weights_hint: dict[str, float], cov: pd.DataFrame,
             max_weight: float = 0.25, method: str = "risk_parity") -> TargetPortfolio:
    """Long-only optimizers on the PIT covariance: risk_parity | min_variance | max_sharpe_tilt."""
    syms = list(cov.columns)
    vols = np.sqrt(np.diag(cov.values).clip(min=1e-10))
    if method == "min_variance":
        inv = 1 / (vols ** 2)
        w = inv / inv.sum()
    elif method == "max_sharpe_tilt":
        er = np.array([weights_hint.get(s, 0.0) for s in syms])
        w = np.clip(er / (vols + 1e-9), 0, None)
        w = w / (w.sum() or 1.0)
    else:  # risk_parity: inverse vol
        inv = 1 / vols
        w = inv / inv.sum()
    w = np.minimum(w, max_weight)
    w = w / (w.sum() or 1.0)
    # expected vol of target
    ev = float(np.sqrt(max(float(w @ cov.values @ w), 0.0)))
    er_p = float(sum(weights_hint.get(s, 0.0) * float(wi) for s, wi in zip(syms, w)))
    return TargetPortfolio({s: round(float(wi), 5) for s, wi in zip(syms, w)},
                           method, round(er_p, 5), round(ev, 5))


@dataclass(frozen=True, slots=True)
class RiskReport:
    var95: float
    cvar95: float
    max_drawdown: float
    concentration_hhi: float
    kill_switch: bool
    kill_reasons: tuple[str, ...]
    stress: dict[str, float]


def evaluate_risk(weights: dict[str, float], rets: pd.DataFrame,
                  capital: float = 1_000_000.0,
                  max_dd: float = 0.20, max_hhi: float = 0.40,
                  max_var_pct: float = 0.05) -> RiskReport:
    """Historical-simulation VaR/CVaR + HHI + stress replays (2008/2020/2022-style)."""
    w = np.array([weights.get(s, 0.0) for s in rets.columns])
    port = rets.fillna(0).values @ w
    var = float(-np.quantile(port, 0.05) * capital) if len(port) else 0.0
    tail = port[port <= np.quantile(port, 0.05)] if len(port) else np.array([0.0])
    cvar = float(-tail.mean() * capital) if len(tail) else var
    cum = (1 + pd.Series(port)).cumprod()
    dd = float(((cum / cum.cummax()) - 1).min()) if len(cum) else 0.0
    hhi = float((w ** 2).sum())
    stress = {
        "2008_gfc_x2vol": round(float(port.std() * -2.5 * capital), 2),
        "2020_covid_crash": round(float(port.min() * 3 * capital) if len(port) else 0.0, 2),
        "2022_rates_shock": round(float(-abs(port.mean()) * 10 * capital), 2),
    }
    reasons: list[str] = []
    if abs(dd) > max_dd:
        reasons.append(f"drawdown {dd:.2%} > {max_dd:.0%}")
    if hhi > max_hhi:
        reasons.append(f"concentration HHI {hhi:.3f} > {max_hhi}")
    if var > capital * max_var_pct:
        reasons.append(f"VaR95 {var:,.0f} > {max_var_pct:.0%} capital")
    return RiskReport(round(var, 2), round(cvar, 2), round(dd, 4), round(hhi, 4),
                      bool(reasons), tuple(reasons), stress)


def pre_trade_check(symbol: str, weight: float, risk: RiskReport,
                    max_order_notional: float, price: float,
                    max_position_pct: float = 0.25) -> tuple[bool, str]:
    if risk.kill_switch:
        return False, f"BLOCKED by kill switch: {'; '.join(risk.kill_reasons)}"
    if weight > max_position_pct:
        return False, f"BLOCKED concentration: {symbol} {weight:.2%} > {max_position_pct:.0%}"
    notional = abs(weight) * 1_000_000
    if notional > max_order_notional:
        return False, f"BLOCKED order cap: {notional:,.0f} > {max_order_notional:,.0f}"
    return True, "PASS pre-trade controls"
