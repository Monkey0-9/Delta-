"""Forecasting model zoo: linear, trees, AR, ensemble, multi-horizon, probabilistic.

Deterministic (fixed seeds). sklearn float boundary documented: inputs are
float64 arrays; parity tolerance rel 1e-9. Research-only; promotion requires
the standard validation gates.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


def _check_xy(X: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    X = np.asarray(X, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    if X.ndim != 2 or y.ndim != 1 or len(X) != len(y) or len(X) < 3:
        raise ValueError("need 2D X and 1D y with >= 3 aligned rows.")
    if not (np.isfinite(X).all() and np.isfinite(y).all()):
        raise ValueError("non-finite values rejected.")
    return X, y


@dataclass(frozen=True, slots=True)
class ModelScore:
    name: str
    mse: float
    mae: float


class OLSModel:
    name = "ols"

    def __init__(self) -> None:
        from sklearn.linear_model import LinearRegression

        self._m = LinearRegression()

    def fit(self, X: np.ndarray, y: np.ndarray) -> OLSModel:
        X, y = _check_xy(X, y)
        self._m.fit(X, y)
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        return np.asarray(self._m.predict(np.asarray(X, dtype=np.float64)))


class RidgeModel:
    name = "ridge"

    def __init__(self, alpha: float = 1.0) -> None:
        from sklearn.linear_model import Ridge

        if alpha <= 0:
            raise ValueError("alpha must be positive.")
        self._m = Ridge(alpha=alpha)

    def fit(self, X: np.ndarray, y: np.ndarray) -> RidgeModel:
        X, y = _check_xy(X, y)
        self._m.fit(X, y)
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        return np.asarray(self._m.predict(np.asarray(X, dtype=np.float64)))


class LassoModel:
    name = "lasso"

    def __init__(self, alpha: float = 0.01, max_iter: int = 5000) -> None:
        from sklearn.linear_model import Lasso

        if alpha <= 0:
            raise ValueError("alpha must be positive.")
        self._m = Lasso(alpha=alpha, max_iter=max_iter)

    def fit(self, X: np.ndarray, y: np.ndarray) -> LassoModel:
        X, y = _check_xy(X, y)
        self._m.fit(X, y)
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        return np.asarray(self._m.predict(np.asarray(X, dtype=np.float64)))


class RandomForestModel:
    name = "random_forest"

    def __init__(self, n_estimators: int = 100) -> None:
        from sklearn.ensemble import RandomForestRegressor

        self._m = RandomForestRegressor(n_estimators=n_estimators, random_state=0, n_jobs=1)

    def fit(self, X: np.ndarray, y: np.ndarray) -> RandomForestModel:
        X, y = _check_xy(X, y)
        self._m.fit(X, y)
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        return np.asarray(self._m.predict(np.asarray(X, dtype=np.float64)))


class GradientBoostingModel:
    name = "gradient_boosting"

    def __init__(self, n_estimators: int = 100) -> None:
        from sklearn.ensemble import GradientBoostingRegressor

        self._m = GradientBoostingRegressor(n_estimators=n_estimators, random_state=0)

    def fit(self, X: np.ndarray, y: np.ndarray) -> GradientBoostingModel:
        X, y = _check_xy(X, y)
        self._m.fit(X, y)
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        return np.asarray(self._m.predict(np.asarray(X, dtype=np.float64)))


class ARModel:
    """Autoregressive AR(p) on a univariate series via Ridge on lag features."""

    name = "ar"

    def __init__(self, lags: int = 5, alpha: float = 1.0) -> None:
        if lags < 1:
            raise ValueError("lags must be >= 1.")
        self._lags = lags
        self._inner = RidgeModel(alpha=alpha)

    @staticmethod
    def lag_matrix(series: np.ndarray, lags: int) -> tuple[np.ndarray, np.ndarray]:
        s = np.asarray(series, dtype=np.float64)
        if s.ndim != 1 or len(s) <= lags:
            raise ValueError("need 1D series longer than lags.")
        X = np.column_stack([s[lags - k - 1 : len(s) - k - 1] for k in range(lags)])
        return X, s[lags:]

    def fit(self, series: np.ndarray) -> ARModel:
        X, y = self.lag_matrix(series, self._lags)
        self._inner.fit(X, y)
        return self

    def predict_next(self, recent: np.ndarray) -> float:
        r = np.asarray(recent, dtype=np.float64)
        if len(r) < self._lags:
            raise ValueError("recent shorter than lags.")
        return float(self._inner.predict(r[-self._lags :].reshape(1, -1))[0])


class QuantileModel:
    """Probabilistic forecast: conditional quantiles via gradient boosting."""

    name = "quantile"

    def __init__(self, quantiles: tuple[float, ...] = (0.1, 0.5, 0.9)) -> None:
        from sklearn.ensemble import GradientBoostingRegressor

        if not quantiles or any(not 0.0 < q < 1.0 for q in quantiles):
            raise ValueError("quantiles must be in (0,1).")
        self._qs = quantiles
        self._models = {
            q: GradientBoostingRegressor(loss="quantile", alpha=q, n_estimators=100, random_state=0)
            for q in quantiles
        }

    def fit(self, X: np.ndarray, y: np.ndarray) -> QuantileModel:
        X, y = _check_xy(X, y)
        for m in self._models.values():
            m.fit(X, y)
        return self

    def predict(self, X: np.ndarray) -> dict[float, np.ndarray]:
        Xa = np.asarray(X, dtype=np.float64)
        return {q: np.asarray(m.predict(Xa)) for q, m in self._models.items()}


class EnsembleModel:
    """Simple average ensemble over fitted members."""

    name = "ensemble"

    def __init__(self, members: list) -> None:
        if not members:
            raise ValueError("members cannot be empty.")
        self._members = members

    def fit(self, X: np.ndarray, y: np.ndarray) -> EnsembleModel:
        for m in self._members:
            m.fit(X, y)
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        preds = np.column_stack([m.predict(X) for m in self._members])
        return preds.mean(axis=1)


def walk_forward_mse(model_fn, X: np.ndarray, y: np.ndarray, *, train: int, test: int, step: int) -> float:
    """Chronological MSE: fit past, score future. Never shuffles."""
    from validation.walk_forward.splitter import walk_forward_splits

    Xa = np.asarray(X, dtype=np.float64)
    ya = np.asarray(y, dtype=np.float64)
    splits = walk_forward_splits(len(ya), train=train, test=test, step=step)
    errors: list[float] = []
    for s in splits:
        m = model_fn().fit(Xa[s.train_start : s.train_end], ya[s.train_start : s.train_end])
        pred = m.predict(Xa[s.test_start : s.test_end])
        errors.extend((float(p) - float(a)) ** 2 for p, a in zip(pred, ya[s.test_start : s.test_end]))
    if not errors:
        raise ValueError("no walk-forward errors produced.")
    return sum(errors) / len(errors)


def compare_models(models: list[tuple[str, object]], X: np.ndarray, y: np.ndarray) -> list[ModelScore]:
    """In-sample fit + full-sample MSE/MAE comparison (research screening only)."""
    Xa = np.asarray(X, dtype=np.float64)
    ya = np.asarray(y, dtype=np.float64)
    out: list[ModelScore] = []
    for name, factory in models:
        m = factory().fit(Xa, ya) if callable(factory) else factory
        pred = np.asarray(m.predict(Xa))
        mse = float(np.mean((pred - ya) ** 2))
        mae = float(np.mean(np.abs(pred - ya)))
        out.append(ModelScore(name, mse, mae))
    return sorted(out, key=lambda s: s.mse)


class MultiHorizonForecaster:
    """One model per horizon: {horizon: fitted model} -> {horizon: prediction}."""

    def __init__(self, model_fn, horizons: tuple[str, ...] = ("1D", "1W", "1M")) -> None:
        if not horizons:
            raise ValueError("horizons cannot be empty.")
        self._fn = model_fn
        self._horizons = horizons
        self._models: dict[str, object] = {}

    def fit(self, X: dict[str, np.ndarray], y: dict[str, np.ndarray]) -> MultiHorizonForecaster:
        for h in self._horizons:
            if h not in X or h not in y:
                raise ValueError(f"missing horizon data: {h}")
            self._models[h] = self._fn().fit(X[h], y[h])
        return self

    def predict(self, X: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
        return {h: np.asarray(self._models[h].predict(np.asarray(X[h], dtype=np.float64))) for h in self._horizons}
