"""
Offline model evaluation helpers for DELTA OS model zoo.

Cross-validation scoring and ranked model comparison using
sklearn/numpy only. No network or LLM calls.

FINANCE SAFETY: generic random K-fold CV leaks the future on time
series and must NEVER drive finance promotion. `cross_val_score_model`
and `compare_models` are screening-only utilities. Finance paths must
call `score_finance_model` (purged walk-forward with embargo) or pass
an explicitly approved protocol; `require_finance_protocol` enforces it.
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping
import numpy as np


#: Protocols approved for finance promotion. Anything else raises.
FINANCE_PROTOCOLS = ("purged_walk_forward", "chronological_holdout")


def require_finance_protocol(protocol: str) -> str:
    """Enforce an explicitly approved finance validation protocol."""
    if protocol not in FINANCE_PROTOCOLS:
        raise ValueError(
            f"protocol {protocol!r} is not approved for finance promotion; "
            f"choose one of {FINANCE_PROTOCOLS}"
        )
    return protocol


def score_finance_model(
    model: Any,
    X: Any,
    y: Any,
    scoring: str = "r2",
    n_splits: int = 3,
    embargo: int = 5,
    protocol: str = "purged_walk_forward",
) -> Dict[str, Any]:
    """Score a model with purged walk-forward splits + embargo gap.

    Chronological TimeSeriesSplit with `embargo` samples dropped after
    each train block (approximating purge for overlapping labels).
    Returns per-fold scores, mean, std, protocol, and embargo.
    """
    from sklearn.base import clone
    from sklearn.model_selection import TimeSeriesSplit

    require_finance_protocol(protocol)
    Xa = np.asarray(X)
    ya = np.asarray(y)
    if len(Xa) != len(ya) or len(Xa) < 2 * (n_splits + 1):
        raise ValueError("need aligned X/y with enough samples for walk-forward")
    tss = TimeSeriesSplit(n_splits=max(2, int(n_splits)))
    scores: List[float] = []
    for train_idx, test_idx in tss.split(Xa):
        train_idx = train_idx[train_idx < (test_idx[0] - embargo)] if embargo else train_idx
        if len(train_idx) < 2 or len(test_idx) < 1:
            continue
        est: Any = clone(model)
        est.fit(Xa[train_idx], ya[train_idx])
        pred = est.predict(Xa[test_idx])
        if scoring == "neg_mean_squared_error":
            scores.append(float(-np.mean((ya[test_idx] - pred) ** 2)))
        else:  # r2 fallback
            ss_res = float(np.sum((ya[test_idx] - pred) ** 2))
            ss_tot = float(np.sum((ya[test_idx] - np.mean(ya[train_idx])) ** 2))
            scores.append(1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0)
    if not scores:
        raise ValueError("no valid walk-forward folds (embargo too large?)")
    return {
        "scores": scores,
        "mean": float(np.mean(scores)),
        "std": float(np.std(scores)),
        "n_splits": len(scores),
        "embargo": embargo,
        "protocol": protocol,
        "scoring": scoring,
    }


def cross_val_score_model(
    model: Any,
    X: Any,
    y: Any,
    cv: int = 3,
    scoring: str = "r2",
    finance: bool = False,
) -> Dict[str, Any]:
    """
    Cross-validate a single estimator.

    SCREENING ONLY for finance data: random K-fold shuffles time and
    leaks the future. Finance promotion must use `score_finance_model`
    (or pass finance_protocol explicitly via `compare_models`).

    Args:
        model: Sklearn-compatible estimator
        X: Feature matrix
        y: Target vector
        cv: Number of CV folds
        scoring: Sklearn scoring name
        finance: If True, route to purged walk-forward scoring instead.

    Returns:
        Dict with ``scores`` list, ``mean``, ``std``, ``cv``,
        and ``scoring`` (plus ``protocol`` when finance=True).
    """
    if finance:
        return score_finance_model(model, X, y, scoring=scoring, n_splits=cv)
    from sklearn.model_selection import cross_val_score

    cv = max(2, int(cv))
    scores = np.asarray(
        cross_val_score(model, X, y, cv=cv, scoring=scoring), dtype=float
    )
    return {
        "scores": [float(s) for s in scores],
        "mean": float(np.mean(scores)),
        "std": float(np.std(scores)),
        "cv": cv,
        "scoring": scoring,
    }


def compare_models(
    models: Mapping[str, Any],
    X: Any,
    y: Any,
    cv: int = 3,
    scoring: str = "r2",
    finance: bool = False,
) -> Dict[str, Dict[str, Any]]:
    """
    Score several estimators and rank by mean score.

    Pass finance=True for time series: routes to purged walk-forward
    scoring. Generic random K-fold ranking is screening-only and must
    never certify finance models.

    Args:
        models: Mapping of model name to estimator
        X: Feature matrix
        y: Target vector
        cv: Number of CV folds
        scoring: Sklearn scoring name

    Returns:
        Ranked dict ``{name: {mean, std, scores, rank}}``
        ordered best-first by mean score.

    Raises:
        ValueError: If models mapping is empty.
    """
    if not models:
        raise ValueError("models must be a non-empty mapping")

    results: Dict[str, Dict[str, Any]] = {}
    for name, model in models.items():
        if finance:
            summary = score_finance_model(model, X, y, scoring=scoring, n_splits=cv)
        else:
            summary = cross_val_score_model(model, X, y, cv=cv, scoring=scoring)
        results[str(name)] = {
            "mean": summary["mean"],
            "std": summary["std"],
            "scores": summary["scores"],
        }

    ranked: List[str] = sorted(
        results.keys(), key=lambda k: results[k]["mean"], reverse=True
    )
    ordered: Dict[str, Dict[str, Any]] = {}
    for rank, name in enumerate(ranked, start=1):
        ordered[name] = {**results[name], "rank": rank}
    return ordered


__all__ = [
    "FINANCE_PROTOCOLS",
    "require_finance_protocol",
    "score_finance_model",
    "cross_val_score_model",
    "compare_models",
]
