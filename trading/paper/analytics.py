"""Paper-trading analytics on equity curves (DELTA OS).

Stdlib only (numpy optional fast-path). All functions accept a plain
list of equity values ordered oldest -> newest.
"""
from __future__ import annotations

from math import sqrt
from typing import List, Sequence, Union

__all__ = ["sharpe", "max_drawdown", "turnover"]

Number = Union[int, float]


def _as_floats(equity: Sequence[Number]) -> List[float]:
    vals = [float(x) for x in equity]
    if any(v != v or v in (float("inf"), float("-inf")) for v in vals):
        raise ValueError("equity curve must be finite.")
    return vals


def _returns(equity: Sequence[float]) -> List[float]:
    return [equity[i] / equity[i - 1] - 1.0 for i in range(1, len(equity)) if equity[i - 1] != 0]


def sharpe(
    equity: Sequence[Number],
    risk_free: float = 0.0,
    periods: int = 252,
) -> float:
    """Annualised Sharpe ratio of an equity curve.

    Args:
        equity: Equity values, oldest first (needs >= 2 points).
        risk_free: Per-period risk-free rate (same frequency as steps).
        periods: Annualisation factor (252 = daily steps).

    Returns:
        Annualised Sharpe; 0.0 when undefined (flat / too short).
    """
    vals = _as_floats(equity)
    if len(vals) < 2 or periods <= 0:
        return 0.0
    rets = [r - risk_free for r in _returns(vals)]
    if len(rets) < 2:
        return 0.0
    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
    if var <= 0:
        return 0.0
    return mean / sqrt(var) * sqrt(periods)


def max_drawdown(equity: Sequence[Number]) -> float:
    """Maximum peak-to-trough drawdown as a positive fraction.

    Returns 0.0 for empty / single-point / never-drawn-down curves.
    """
    vals = _as_floats(equity)
    if len(vals) < 2:
        return 0.0
    peak = vals[0]
    worst = 0.0
    for v in vals[1:]:
        if v > peak:
            peak = v
        elif peak > 0:
            dd = (peak - v) / peak
            if dd > worst:
                worst = dd
    return max(worst, 0.0)


def turnover(
    equity: Sequence[Number],
    traded: Union[Sequence[Number], None] = None,
) -> float:
    """Portfolio turnover vs average equity.

    With explicit per-step traded notional: sum(|traded|) / mean(equity).
    Without it (equity curve only): sum(|dEquity|) / mean(|equity|), a
    churn proxy — pass traded notionals for a true turnover figure.
    """
    vals = _as_floats(equity)
    if not vals:
        return 0.0
    avg = sum(abs(v) for v in vals) / len(vals)
    if avg <= 0:
        return 0.0
    if traded is None:
        churn = sum(abs(vals[i] - vals[i - 1]) for i in range(1, len(vals)))
        return churn / avg
    flow = [abs(float(x)) for x in traded]
    return sum(flow) / avg
