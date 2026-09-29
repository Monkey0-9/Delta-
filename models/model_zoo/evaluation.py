"""
Offline model evaluation helpers for DELTA OS model zoo.

Cross-validation scoring and ranked model comparison using
sklearn/numpy only. No network or LLM calls.
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping
import numpy as np


def cross_val_score_model(
    model: Any,
    X: Any,
    y: Any,
    cv: int = 3,
    scoring: str = "r2",
) -> Dict[str, Any]:
    """
    Cross-validate a single estimator.

    Args:
        model: Sklearn-compatible estimator
        X: Feature matrix
        y: Target vector
        cv: Number of CV folds
        scoring: Sklearn scoring name

    Returns:
        Dict with ``scores`` list, ``mean``, ``std``, ``cv``,
        and ``scoring``.
    """
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
) -> Dict[str, Dict[str, Any]]:
    """
    Score several estimators and rank by mean CV score.

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
    "cross_val_score_model",
    "compare_models",
]
