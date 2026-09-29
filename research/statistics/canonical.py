"""Canonical statistical validation home (P1 slice).

Single source of truth for multiple-testing-adjusted performance:
Bailey–Lopez de Prado Deflated Sharpe Ratio + Lopez de Prado CSCV/CPCV
Probability of Backtest Overfitting.

`delta_omega.alpha_risk` holds the vetted math; this module is the
research-side front door, adding:
  - `cpcv_pbo`: full S-splits x N-trials PBO from a returns panel
    (replaces top-half-loss approximations wherever trial panels exist)
  - `pbo_single_split`: honest labeled fallback when only one split exists
    (returns 0.0/1.0 rank verdict, never a blended heuristic)
  - `dsr_report`: DSR with method provenance for experiment manifests

Every function records its method name so manifests never present a
proxy as a definitive statistic.
"""
from __future__ import annotations

import math

import numpy as np

from delta_omega.alpha_risk import cpcv_splits, deflated_sharpe, pbo

METHOD_DSR = "bailey-ldp-dsr-via-delta-omega"
METHOD_PBO_CPCV = "ldp-cpcv-pbo"
METHOD_PBO_SINGLE = "single-split-rank-fallback"


def sharpe_ann(returns: np.ndarray) -> float:
    """Annualized Sharpe (252d) of a return slice; 0.0 on degenerate input."""
    r = np.asarray(returns, dtype=float)
    r = r[np.isfinite(r)]
    if r.size < 2 or float(r.std()) <= 0:
        return 0.0
    return float(r.mean() / r.std() * math.sqrt(252.0))


def cpcv_pbo(returns_panel: np.ndarray, n_partitions: int = 6,
             n_test: int = 2, embargo_pct: float = 0.01) -> dict:
    """Full CPCV PBO over a (T, N) panel of trial returns.

    Each CPCV train/test index combo yields one IS/OOS Sharpe row;
    PBO = fraction of splits where the IS-best trial ranks below
    median OOS. Returns {pbo, n_splits, method}.
    """
    panel = np.asarray(returns_panel, dtype=float)
    if panel.ndim != 2 or panel.shape[0] < n_partitions or panel.shape[1] < 1:
        raise ValueError("returns_panel must be (T, N) with T >= n_partitions.")
    is_rows, oos_rows = [], []
    n_splits = 0
    n_skipped = 0
    for item in _iter_cpcv(panel.shape[0], n_partitions,
                           n_test, embargo_pct):
        if item is None:
            n_skipped += 1
            continue
        train_idx, test_idx = item
        is_rows.append([sharpe_ann(panel[train_idx, j])
                        for j in range(panel.shape[1])])
        oos_rows.append([sharpe_ann(panel[test_idx, j])
                         for j in range(panel.shape[1])])
        n_splits += 1
    if n_splits < 2:
        raise ValueError("fewer than 2 feasible CPCV splits for this geometry.")
    value = pbo(np.asarray(is_rows), np.asarray(oos_rows))
    return {"pbo": float(value), "n_splits": n_splits,
            "n_skipped": n_skipped, "method": METHOD_PBO_CPCV}


def _iter_cpcv(n_obs: int, n_partitions: int, n_test: int, embargo_pct: float):
    """Yield feasible CPCV splits, skipping combos whose embargo purges the
    entire train set (non-contiguous test blocks spanning the full range).
    Skips are counted in the report — never silent in the manifest."""
    from itertools import combinations
    import numpy as _np
    bounds = _np.array_split(_np.arange(n_obs), n_partitions)
    embargo = max(1, int(n_obs * embargo_pct))
    for test_parts in combinations(range(n_partitions), n_test):
        test_idx = _np.concatenate([bounds[i] for i in test_parts])
        lo, hi = int(test_idx.min()), int(test_idx.max())
        train_idx = _np.concatenate(
            [bounds[i] for i in range(n_partitions) if i not in test_parts])
        train_idx = train_idx[(train_idx < lo - embargo) | (train_idx > hi + embargo)]
        if train_idx.size == 0:
            yield None  # sentinel: infeasible combo
        else:
            yield train_idx, test_idx


def pbo_single_split(is_sharpes: list[float] | np.ndarray,
                     oos_sharpes: list[float] | np.ndarray) -> dict:
    """Honest single-split fallback: 1.0 if the IS-best trial is at/below
    median OOS, else 0.0. Labeled as fallback — prefer `cpcv_pbo`."""
    a = np.asarray(list(is_sharpes), dtype=float)
    b = np.asarray(list(oos_sharpes), dtype=float)
    n = min(a.size, b.size)
    if n < 2 or not np.all(np.isfinite(a[:n])) or not np.all(np.isfinite(b[:n])):
        return {"pbo": float("nan"), "method": METHOD_PBO_SINGLE,
                "reason": "insufficient-finite-pairs"}
    a, b = a[:n], b[:n]
    best = int(np.argmax(a))
    rank = int((b > b[best]).sum()) + 1  # 1 = best
    verdict = 1.0 if rank > (n + 1) / 2 else 0.0
    return {"pbo": verdict, "method": METHOD_PBO_SINGLE,
            "is_best": best, "oos_rank": rank, "n": n}


def dsr_report(sr: float, n_trials: int, n_obs: int, skew: float = 0.0,
               kurt: float = 3.0) -> dict:
    """DSR value + method provenance for manifests."""
    return {"dsr": float(deflated_sharpe(sr, n_trials, n_obs, skew, kurt)),
            "method": METHOD_DSR, "n_trials": int(n_trials), "n_obs": int(n_obs)}


__all__ = ["METHOD_DSR", "METHOD_PBO_CPCV", "METHOD_PBO_SINGLE",
           "cpcv_pbo", "cpcv_splits", "deflated_sharpe", "dsr_report",
           "pbo", "pbo_single_split", "sharpe_ann"]
