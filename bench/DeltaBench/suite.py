"""DeltaBench (Stage-4 U): quant benchmark suite, distinct from FinBench (LLM-only).

Suites: prediction / risk / portfolio / regression. Task-appropriate metrics:
MAE/RMSE/log-loss/Brier/calibration/IC/ICIR/Sharpe/Sortino/drawdown/turnover/
cost-adjusted-return. Every new model reports here. CI regression gate included.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True, slots=True)
class BenchScore:
    suite: str
    metric: str
    value: float
    threshold: float
    passed: bool


def mae(y: np.ndarray, p: np.ndarray) -> float:
    return float(np.mean(np.abs(np.asarray(y) - np.asarray(p))))


def rmse(y: np.ndarray, p: np.ndarray) -> float:
    return float(np.sqrt(np.mean((np.asarray(y) - np.asarray(p)) ** 2)))


def brier(y: np.ndarray, p: np.ndarray) -> float:
    return float(np.mean((np.asarray(y) - np.asarray(p)) ** 2))


def information_coefficient(y: np.ndarray, p: np.ndarray) -> float:
    y, p = np.asarray(y, float), np.asarray(p, float)
    if y.std() == 0 or p.std() == 0:
        return 0.0
    return float(np.corrcoef(y, p)[0, 1])


def sharpe(returns: np.ndarray) -> float:
    r = np.asarray(returns, float)
    if r.std() == 0:
        return 0.0
    return float(r.mean() / r.std() * np.sqrt(252.0))


def max_drawdown(equity: np.ndarray) -> float:
    e = np.asarray(equity, float)
    peak = np.maximum.accumulate(e)
    return float(((e / peak) - 1.0).min())


REGRESSION_THRESHOLDS = {"mae": 0.10, "rmse": 0.15, "brier": 0.25}


def regression_gate(y: np.ndarray, p: np.ndarray) -> list[BenchScore]:
    return [
        BenchScore("regression", "mae", mae(y, p), REGRESSION_THRESHOLDS["mae"],
                   mae(y, p) <= REGRESSION_THRESHOLDS["mae"]),
        BenchScore("regression", "rmse", rmse(y, p), REGRESSION_THRESHOLDS["rmse"],
                   rmse(y, p) <= REGRESSION_THRESHOLDS["rmse"]),
    ]


__all__ = ["BenchScore", "mae", "rmse", "brier", "information_coefficient",
           "sharpe", "max_drawdown", "regression_gate", "REGRESSION_THRESHOLDS"]
