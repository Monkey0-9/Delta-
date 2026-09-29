"""Advanced validation metrics for alpha and strategy research."""

from __future__ import annotations

from typing import Optional
import numpy as np


def rank_ic(signal: np.ndarray, forward_returns: np.ndarray) -> float:
    """Spearman rank information coefficient."""
    from scipy.stats import spearmanr

    s = np.asarray(signal, dtype=float).ravel()
    f = np.asarray(forward_returns, dtype=float).ravel()
    mask = np.isfinite(s) & np.isfinite(f)
    if mask.sum() < 3:
        return 0.0
    rho, _ = spearmanr(s[mask], f[mask])
    return 0.0 if not np.isfinite(rho) else float(rho)


def icir(signal: np.ndarray, forward_returns: np.ndarray) -> float:
    """IC information ratio: mean(IC_t) / std(IC_t) over time.

    Accepts 2-D panels (T, N) computing per-period rank IC, or 1-D
    vectors returning 0.0 (single IC has no time variation).
    """
    s = np.asarray(signal, dtype=float)
    f = np.asarray(forward_returns, dtype=float)
    if s.ndim == 1:
        return 0.0
    ics = np.asarray([rank_ic(s[t], f[t]) for t in range(s.shape[0])], dtype=float)
    ics = ics[np.isfinite(ics)]
    if len(ics) < 2 or ics.std(ddof=1) == 0:
        return 0.0
    return float(ics.mean() / ics.std(ddof=1))


def deflated_sharpe_ratio(
    sharpe: float, n_trials: int, skew: float = 0.0, kurt: float = 3.0, n_obs: int = 252
) -> float:
    """Deflated Sharpe Ratio (Bailey & Lopez de Prado, simplified).

    Returns PSR against the expected Sharpe under multiple testing.
    """
    from scipy.stats import norm

    n_trials = max(int(n_trials), 1)
    gamma3, gamma4 = float(skew), float(kurt)
    sr0 = np.sqrt(max(n_obs, 1)) * (
        (1 - np.euler_gamma) * norm.ppf(1 - 1.0 / n_trials)
        + np.euler_gamma * norm.ppf(1 - 1.0 / (n_trials * np.e))
    ) / max(n_obs - 1, 1)
    denom = np.sqrt(max(1 - gamma3 * sharpe + (gamma4 - 1) / 4 * sharpe ** 2, 1e-12)
                    / max(n_obs - 1, 1))
    return float(norm.cdf((sharpe - sr0) / denom))


def probability_backtest_overfitting(
    returns_matrix: np.ndarray, n_splits: int = 8
) -> float:
    """Simplified PBO (Bailey et al.) via IS/OOS split.

    Splits trials into IS (first half) and OOS (second half) blocks,
    ranks by IS Sharpe, and measures how often IS-top trials fall
    below the OOS median. Returns value in [0, 1]; lower is better.
    """
    R = np.asarray(returns_matrix, dtype=float)
    if R.ndim != 2 or R.shape[1] < 4:
        return 0.0
    T, N = R.shape
    half = T // 2
    if half < 2:
        return 0.0
    IS, OOS = R[:half], R[half:]
    is_sr = IS.mean(0) / np.maximum(IS.std(ddof=1), 1e-12)
    oos_sr = OOS.mean(0) / np.maximum(OOS.std(ddof=1), 1e-12)
    order = np.argsort(-is_sr)
    n_top = max(N // 2, 1)
    top = order[:n_top]
    med = float(np.median(oos_sr))
    under = sum(1 for j in top if oos_sr[j] < med)
    return float(np.clip(under / max(len(top), 1), 0.0, 1.0))


def newey_west_tstat(residuals: np.ndarray, lags: Optional[int] = None) -> float:
    """Newey-West HAC-adjusted t-stat of mean != 0."""
    e = np.asarray(residuals, dtype=float).ravel()
    e = e[np.isfinite(e)]
    n = len(e)
    if n < 3:
        return 0.0
    if lags is None:
        lags = int(np.floor(4 * (n / 100) ** (2 / 9)))
    lags = max(min(int(lags), n - 1), 0)
    mean = e.mean()
    gamma0 = ((e - mean) ** 2).sum() / n
    s2 = gamma0
    for lag in range(1, lags + 1):
        w = 1 - lag / (lags + 1)
        cov = ((e[lag:] - mean) * (e[:-lag] - mean)).sum() / n
        s2 += 2 * w * cov
    se = np.sqrt(max(s2, 1e-12) / n)
    return float(mean / se) if se > 0 else 0.0


def bonferroni_holm(p_values: np.ndarray, alpha: float = 0.05) -> np.ndarray:
    """Holm step-down correction; returns per-hypothesis reject flags."""
    p = np.asarray(p_values, dtype=float).ravel()
    m = len(p)
    reject = np.zeros(m, dtype=bool)
    order = np.argsort(p)
    for rank, idx in enumerate(order):
        if p[idx] <= alpha / max(m - rank, 1):
            reject[idx] = True
        else:
            break
    return reject


__all__ = [
    "rank_ic",
    "icir",
    "deflated_sharpe_ratio",
    "probability_backtest_overfitting",
    "newey_west_tstat",
    "bonferroni_holm",
]
