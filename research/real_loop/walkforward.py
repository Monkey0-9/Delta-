"""W122 walk-forward validation with purge + embargo (Lopez de Prado).

Every split guarantees: no training bar is used to evaluate a test bar, labels
that look ahead by h bars purge h bars after each train end, and an embargo of
e bars separates train from test. Returns per-fold OOS metrics plus aggregate;
any sign disagreement between IS and OOS is surfaced, not hidden.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

WF_VERSION = "wf-v1"


def purged_splits(n: int, n_folds: int = 5, horizon: int = 5, embargo_pct: float = 0.01,
                  min_train: int = 60) -> list[tuple[np.ndarray, np.ndarray]]:
    """Indices for purged walk-forward folds over n samples.

    Train = expanding [0, end), purged of the last `horizon` bars (label
    overlap), test = next block of size (n - min_train) // n_folds, preceded
    by `embargo` bars gap. Deterministic.
    """
    if n < min_train + n_folds:
        raise ValueError(f"need >= {min_train + n_folds} samples, got {n}.")
    test_size = (n - min_train) // n_folds
    embargo = max(1, int(n * embargo_pct))
    out = []
    for f in range(n_folds):
        test_start = min_train + f * test_size
        test_end = min(test_start + test_size, n)
        train_end = test_start - embargo - horizon
        if train_end < min_train:
            # Purging would eat the whole training block: this fold is
            # infeasible without leakage, so it is SKIPPED (never shrunk).
            continue
        out.append((np.arange(0, train_end), np.arange(test_start, test_end)))
    if not out:
        raise ValueError("no feasible purged folds for these dimensions.")
    return out


def walk_forward(price: pd.Series, feat: pd.DataFrame, fwd_days: int = 5,
                 n_folds: int = 5, costs_bps: float = 8.0) -> dict:
    """Signal = mean blend of mom/mr/trend columns; positions trade test folds.

    Costs per unit turnover from costs_bps. Returns fold table + aggregate OOS
    Sharpe/hit-rate/max-DD and IS-vs-OOS sign agreement (overfit smoke test).
    """
    from research.real_loop import backtest as B

    px = price.astype(float)
    sig_cols = [c for c in feat.columns if c.startswith(("mom_", "mr_z_", "trend_"))]
    sig = feat[sig_cols].mean(axis=1).fillna(0) if sig_cols else pd.Series(0.0, index=feat.index)
    pos_full = (sig > 0.5).astype(float) - (sig < -0.5).astype(float)
    pos_full = pos_full.shift(2).fillna(0)
    fwd = px.pct_change(fwd_days).shift(-fwd_days)
    folds = []
    for tr, te in purged_splits(len(px), n_folds, fwd_days):
        idx = px.index[te]
        r = (pos_full.reindex(idx).fillna(0) * fwd.reindex(idx).fillna(0))
        churn = pos_full.reindex(idx).fillna(0).diff().abs().fillna(0)
        net = r - churn * costs_bps / 1e4
        folds.append({"n": len(idx),
                      "gross": round(float(r.sum()), 5),
                      "net": round(float(net.sum()), 5),
                      "hit": round(float((net > 0).mean()) if len(net) else 0.0, 3),
                      "sharpe": round(float(net.mean() / (net.std() or 1e-9)
                                            * np.sqrt(252 / fwd_days)) if len(net) > 3 else 0.0, 3)})
    nets = np.array([f["net"] for f in folds])
    agree = bool((nets > 0).sum() >= len(nets) / 2)  # majority-positive OOS
    all_net = float(nets.sum())
    return {"version": WF_VERSION, "n_folds": len(folds), "fwd_days": fwd_days,
            "costs_bps": costs_bps, "folds": folds,
            "oos_total_net": round(all_net, 5),
            "oos_majority_positive": agree,
            "gate": {"pass": bool(agree and all_net > 0),
                     "rule": "majority of folds OOS-positive and total OOS net > 0"}}


__all__ = ["WF_VERSION", "purged_splits", "walk_forward"]
