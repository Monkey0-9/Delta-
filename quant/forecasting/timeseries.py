"""Classical time-series models: ARIMA (statsmodels), Holt linear trend, seasonal naive.

Deterministic given data (statsmodels MLE is deterministic; no random restarts).
Research-only; promotion requires the standard validation gates.
"""
from __future__ import annotations

import numpy as np


def _series(values: np.ndarray, min_len: int) -> np.ndarray:
    s = np.asarray(values, dtype=np.float64)
    if s.ndim != 1 or len(s) < min_len:
        raise ValueError(f"need 1D series with >= {min_len} points.")
    if not np.isfinite(s).all():
        raise ValueError("non-finite values rejected.")
    return s


class ARIMAModel:
    name = "arima"

    def __init__(self, order: tuple[int, int, int] = (1, 1, 1)) -> None:
        p, d, q = order
        if p < 0 or d < 0 or q < 0 or p + d + q == 0:
            raise ValueError("invalid ARIMA order.")
        self._order = order
        self._fit = None

    def fit(self, series: np.ndarray) -> ARIMAModel:
        from statsmodels.tsa.arima.model import ARIMA

        s = _series(series, 8)
        self._fit = ARIMA(s, order=self._order).fit()
        return self

    def forecast(self, steps: int) -> np.ndarray:
        if self._fit is None:
            raise ValueError("model not fitted.")
        if steps < 1:
            raise ValueError("steps must be >= 1.")
        return np.asarray(self._fit.forecast(steps=steps), dtype=np.float64)


class HoltTrend:
    """Holt's linear trend (level + slope exponential smoothing)."""

    name = "holt"

    def __init__(self, alpha: float = 0.3, beta: float = 0.1) -> None:
        if not 0.0 < alpha <= 1.0 or not 0.0 < beta <= 1.0:
            raise ValueError("alpha/beta must be in (0,1].")
        self._a, self._b = alpha, beta
        self._level = 0.0
        self._slope = 0.0
        self._fitted = False

    def fit(self, series: np.ndarray) -> HoltTrend:
        s = _series(series, 3)
        level, slope = float(s[0]), float(s[1] - s[0])
        for x in s[1:]:
            prev_level = level
            level = self._a * float(x) + (1 - self._a) * (level + slope)
            slope = self._b * (level - prev_level) + (1 - self._b) * slope
        self._level, self._slope, self._fitted = level, slope, True
        return self

    def forecast(self, steps: int) -> np.ndarray:
        if not self._fitted:
            raise ValueError("model not fitted.")
        if steps < 1:
            raise ValueError("steps must be >= 1.")
        return np.array([self._level + h * self._slope for h in range(1, steps + 1)])


class SeasonalNaive:
    """Repeat the value from one season ago. Honest baseline."""

    name = "seasonal_naive"

    def __init__(self, season: int = 5) -> None:
        if season < 1:
            raise ValueError("season must be >= 1.")
        self._season = season
        self._tail: np.ndarray | None = None

    def fit(self, series: np.ndarray) -> SeasonalNaive:
        s = _series(series, self._season)
        self._tail = s[-self._season :]
        return self

    def forecast(self, steps: int) -> np.ndarray:
        if self._tail is None:
            raise ValueError("model not fitted.")
        if steps < 1:
            raise ValueError("steps must be >= 1.")
        idx = np.arange(steps) % self._season
        return self._tail[idx].copy()
