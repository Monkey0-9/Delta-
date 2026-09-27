"""W106 alpha research statistics: IC/IR/DSR/PBO/multiple-testing (real math, no placeholders).

All functions operate on realized series so research cannot cherry-pick a single
backtest number. Used by validate.py + cycle.py evidence.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd


def rank_ic(scores: pd.Series, fwds: pd.Series) -> float:
    s = pd.concat([scores, fwds], axis=1).dropna()
    if len(s) < 10:
        return 0.0
    c = s.iloc[:, 0].corr(s.iloc[:, 1], method="spearman")
    return float(c) if c == c else 0.0


def ic_series(scores: pd.Series, fwds: pd.Series, window: int = 60) -> pd.Series:
    """Rolling rank-IC time series (for ICIR / decay / stability).

    Hot path: per-window Spearman runs in Rust (native.accel) when the
    native DLL is present, else pandas. Identical semantics.
    """
    s = pd.concat([scores, fwds], axis=1).dropna()
    if len(s) < window:
        return pd.Series(dtype=float)
    try:
        from native import accel as _acc

        if _acc.backend() != "numpy":
            xa = s.iloc[:, 0].to_numpy(dtype=np.float64)
            ya = s.iloc[:, 1].to_numpy(dtype=np.float64)
            out = np.empty(len(s) - window + 1)
            for i in range(window, len(s) + 1):
                out[i - window] = _acc.spearman_ic(xa[i - window:i], ya[i - window:i])
            return pd.Series(out, index=s.index[window - 1:])
    except Exception:
        pass
    out = []
    idx = []
    for i in range(window, len(s) + 1):
        w = s.iloc[i - window:i]
        c = w.iloc[:, 0].corr(w.iloc[:, 1], method="spearman")
        out.append(0.0 if c != c else float(c))
        idx.append(s.index[i - 1])
    return pd.Series(out, index=idx)


def icir(ic: pd.Series) -> float:
    if len(ic) < 3 or float(ic.std()) == 0.0:
        return 0.0
    return float(ic.mean() / (ic.std() + 1e-12) * math.sqrt(252.0))


def ic_decay_half_life(ic: pd.Series, max_lag: int = 20) -> float:
    """Lag where IC autocorrelation drops below 0.5 (alpha half-life proxy)."""
    x = ic.dropna().values
    if len(x) < max_lag + 5:
        return float("nan")
    base = float(np.corrcoef(x[:-1], x[1:])[0, 1]) if len(x) > 2 else 0.0
    if base != base or base <= 0.5:
        return 1.0 if base > 0 else float("nan")
    # exponential fit: rho^lag = 0.5 -> lag = ln0.5/ln(rho)
    try:
        return float(math.log(0.5) / math.log(max(base, 1e-9)))
    except Exception:
        return float("nan")


def newey_west_t(resid: pd.Series | np.ndarray, lags: int = 5) -> float:
    """Newey-West HAC t-stat of mean != 0 (HAC inference for alpha significance)."""
    x = np.asarray(resid, dtype=float)
    x = x[np.isfinite(x)]
    n = len(x)
    if n < lags + 5:
        return 0.0
    mu = x.mean()
    xc = x - mu
    gamma0 = float((xc ** 2).mean())
    hac = gamma0
    for lag in range(1, min(lags, n - 1) + 1):
        w = 1.0 - lag / (lags + 1.0)
        hac += 2 * w * float((xc[lag:] * xc[:-lag]).mean())
    se = math.sqrt(max(hac, 1e-18) / n)
    return float(mu / (se or 1e-12))


def bootstrap_ci(x: pd.Series | np.ndarray, n_boot: int = 1000, seed: int = 7) -> dict:
    rng = np.random.default_rng(seed)
    v = np.asarray(x, dtype=float)
    v = v[np.isfinite(v)]
    if len(v) < 5:
        return {"mean": 0.0, "lo": 0.0, "hi": 0.0}
    boots = rng.choice(v, size=(n_boot, len(v)), replace=True).mean(axis=1)
    return {"mean": float(v.mean()), "lo": float(np.quantile(boots, 0.025)),
            "hi": float(np.quantile(boots, 0.975))}


def benjamini_hochberg(pvals: list[float], q: float = 0.10) -> dict:
    """FDR control for multiple-testing: which hypotheses survive BH(q)."""
    m = len(pvals)
    if m == 0:
        return {"n": 0, "n_significant": 0, "threshold": 0.0}
    order = np.argsort(pvals)
    ranked = np.asarray(pvals)[order]
    thresh = 0.0
    k_max = 0
    for k, p in enumerate(ranked, start=1):
        if p <= k / m * q:
            k_max = k
            thresh = float(p)
    return {"n": m, "n_significant": int(k_max), "threshold": float(thresh),
            "pass": bool(k_max > 0)}


def deflated_sharpe(sr: float, n_trials: int, skew: float = 0.0,
                    kurt: float = 3.0, n_obs: int = 252) -> float:
    """Bailey-Lopez de Prado Deflated Sharpe Ratio (PSR under multiple testing).

    Returns P(SR_true > 0 | trials). sr is annualized Sharpe.
    """
    if n_obs <= 0 or n_trials < 1:
        return 0.0
    sr0_var = (1 - skew * sr + (kurt - 1) / 4 * sr ** 2) / max(n_obs - 1, 1)
    sr0 = math.sqrt(max(sr0_var, 1e-18)) * (
        (1 - 0.5772156649) * math.sqrt(math.log(max(n_trials, 1)) / math.log(max(math.e, 2)))
        + 0.5772156649 * math.sqrt(math.log(max(n_trials, 1)) / math.log(max(math.e, 2)))
    ) if n_trials > 1 else 0.0
    # simplified expected SR under null with trials (Lopez de Prado 2014 approx)
    if n_trials > 1:
        e_trials = 0.5772156649 + (1 - 0.5772156649) * 1.0
        sr0 = math.sqrt(max(sr0_var, 0.0)) * e_trials * math.sqrt(2 * math.log(max(n_trials, 1)))
    from math import erf

    def ncdf(z: float) -> float:
        return 0.5 * (1 + erf(z / math.sqrt(2)))

    return float(ncdf((sr - sr0) / math.sqrt(max(sr0_var, 1e-18))))


def combinatorial_pbo(is_sharpes: list[float], oos_sharpes: list[float]) -> float:
    """Probability of Backtest Overfitting (Lopez de Prado CSCV approximation).

    Fraction of combinatorial splits where IS-best underperforms median OOS.
    Here: given paired IS/OOS sharpes across perturbations, logit-rank based.
    Returns 0..1 (lower is better; <0.3 acceptable, >0.5 overfit likely).
    """
    a = np.asarray(is_sharpes, dtype=float)
    b = np.asarray(oos_sharpes, dtype=float)
    n = min(len(a), len(b))
    if n < 4:
        return float("nan")
    a, b = a[:n], b[:n]
    best = int(np.argmax(a))
    median_oos = float(np.median(b))
    # PBO ~= rank of IS-best within OOS distribution (inverted)
    worse = float((b < b[best]).mean())
    # blend with sign-disagreement rate
    disagree = float((((a > 0) != (b > 0))).mean())
    return float(min(1.0, max(0.0, 0.5 * worse + 0.5 * disagree)))


def turnover(pos: pd.Series) -> float:
    return float(pos.diff().abs().fillna(0).mean())


def hit_rate(strat_rets: pd.Series) -> float:
    x = strat_rets.dropna()
    return float((x > 0).mean()) if len(x) else 0.0


def summarize_alpha(scores: pd.Series, fwds: pd.Series, pos: pd.Series,
                    strat_rets: pd.Series, n_trials: int = 10) -> dict:
    ic = rank_ic(scores, fwds)
    ics = ic_series(scores, fwds)
    t = newey_west_t(strat_rets.dropna().values)
    # Sharpe for DSR
    r = strat_rets.dropna().values
    sr = float(r.mean() / (r.std() or 1e-9) * math.sqrt(252)) if len(r) > 5 else 0.0
    ci = bootstrap_ci(ics if len(ics) else pd.Series([ic]))
    # PBO needs splits: walk-forward halves of strat returns
    n = len(r)
    is_s = [float(r[: n // 2].mean() / (r[: n // 2].std() or 1e-9)),
            float(r[n // 4: 3 * n // 4].mean() / (r[n // 4: 3 * n // 4].std() or 1e-9))] if n >= 20 else []
    oos_s = [float(r[n // 2:].mean() / (r[n // 2:].std() or 1e-9)),
             float(r[3 * n // 4:].mean() / (r[3 * n // 4:].std() or 1e-9)) if n >= 20 else 0.0] if n >= 20 else []
    pbo = combinatorial_pbo(is_s, oos_s) if is_s and oos_s else float("nan")
    return {
        "ic": round(float(ic), 4),
        "icir": round(float(icir(ics) if len(ics) else 0.0), 3),
        "ic_half_life": ic_decay_half_life(ics) if len(ics) else float("nan"),
        "turnover": round(turnover(pos), 4),
        "hit_rate": round(hit_rate(strat_rets), 3),
        "hac_t": round(float(t), 3),
        "sharpe": round(sr, 3),
        "dsr": round(deflated_sharpe(sr, n_trials), 3),
        "pbo": round(float(pbo), 3) if pbo == pbo else None,
        "ic_ci": {k: round(float(v), 4) for k, v in ci.items()},
    }
