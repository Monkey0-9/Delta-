"""
Model factory for DELTA OS model zoo.

Builds offline sklearn regressors by kind string. NumPy/sklearn
only; no network or LLM calls.
"""

from __future__ import annotations

from typing import Any


_KIND_ALIASES = {
    "ridge": "ridge",
    "lasso": "lasso",
    "random_forest": "random_forest",
    "randomforest": "random_forest",
    "rf": "random_forest",
    "gradient_boosting": "gradient_boosting",
    "gradientboosting": "gradient_boosting",
    "gbm": "gradient_boosting",
    "gbr": "gradient_boosting",
    "naive": "naive",
    "dummy": "naive",
    "mean": "naive",
}


def _normalize_kind(kind: str) -> str:
    """Normalize user kind string to canonical key."""
    if not isinstance(kind, str):
        raise ValueError("kind must be a string")
    key = kind.strip().lower().replace("-", "_").replace(" ", "_")
    canonical = _KIND_ALIASES.get(key, key)
    if canonical not in ("ridge", "lasso", "random_forest",
                         "gradient_boosting", "naive"):
        raise ValueError(
            f"Unknown model kind '{kind}'. Expected one of: "
            "ridge, lasso, random_forest, gradient_boosting, naive."
        )
    return canonical


def make_model(kind: str, **kwargs: Any) -> Any:
    """
    Create a regressor by kind string.

    Args:
        kind: One of ``ridge``, ``lasso``, ``random_forest``,
            ``gradient_boosting``, ``naive`` (aliases accepted).
        **kwargs: Constructor overrides (e.g. ``alpha=1.0``,
            ``random_state=42``).

    Returns:
        Unfitted sklearn regressor instance.

    Raises:
        ValueError: If kind is unknown.
    """
    canonical = _normalize_kind(kind)

    if canonical == "ridge":
        from sklearn.linear_model import Ridge
        params = {"alpha": 1.0, "random_state": 42}
        params.update(kwargs)
        return Ridge(**params)

    if canonical == "lasso":
        from sklearn.linear_model import Lasso
        params = {"alpha": 1.0, "max_iter": 5000, "random_state": 42}
        params.update(kwargs)
        return Lasso(**params)

    if canonical == "random_forest":
        from sklearn.ensemble import RandomForestRegressor
        params = {"n_estimators": 100, "random_state": 42, "n_jobs": -1}
        params.update(kwargs)
        return RandomForestRegressor(**params)

    if canonical == "gradient_boosting":
        from sklearn.ensemble import GradientBoostingRegressor
        params = {"random_state": 42}
        params.update(kwargs)
        return GradientBoostingRegressor(**params)

    # naive: mean predictor, useful as an offline baseline.
    from sklearn.dummy import DummyRegressor
    params = {"strategy": "mean"}
    params.update(kwargs)
    return DummyRegressor(**params)


__all__ = [
    "make_model",
]
