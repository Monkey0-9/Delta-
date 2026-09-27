from __future__ import annotations

import math
from typing import Iterable

import numpy as np

from .contracts import MetricResult


def _clean(values: Iterable[float]) -> np.ndarray:
    x = np.asarray(
        list(values),
        dtype=float,
    )

    x = x[np.isfinite(x)]

    if len(x) == 0:
        raise ValueError(
            "No finite observations."
        )

    return x


def max_drawdown(returns: np.ndarray) -> float:
    equity = np.cumprod(
        1.0 + returns
    )

    peak = np.maximum.accumulate(
        equity
    )

    drawdown = equity / peak - 1.0

    return float(drawdown.min())


def sharpe(
    returns: np.ndarray,
    annualization: int = 252,
) -> float:

    if returns.std(ddof=1) == 0:
        return 0.0

    return float(
        np.sqrt(annualization)
        * returns.mean()
        / returns.std(ddof=1)
    )


def sortino(
    returns: np.ndarray,
    annualization: int = 252,
) -> float:

    downside = np.minimum(
        returns,
        0.0,
    )

    denominator = np.sqrt(
        np.mean(downside**2)
    )

    if denominator == 0:
        return 0.0

    return float(
        np.sqrt(annualization)
        * returns.mean()
        / denominator
    )


def annualized_return(
    returns: np.ndarray,
    annualization: int = 252,
) -> float:

    years = len(returns) / annualization

    if years <= 0:
        return 0.0

    wealth = np.prod(
        1.0 + returns
    )

    if wealth <= 0:
        return -1.0

    return float(
        wealth ** (1 / years) - 1
    )


def bootstrap_mean_ci(
    returns: np.ndarray,
    seed: int = 42,
    samples: int = 10_000,
) -> tuple[float, float]:

    rng = np.random.default_rng(seed)

    draws = rng.choice(
        returns,
        size=(samples, len(returns)),
        replace=True,
    )

    means = draws.mean(axis=1)

    return (
        float(np.quantile(means, 0.025)),
        float(np.quantile(means, 0.975)),
    )


def newey_west_tstat(
    returns: np.ndarray,
    lags: int | None = None,
) -> float:

    x = returns - returns.mean()

    n = len(x)

    if n < 5:
        return 0.0

    if lags is None:
        lags = int(
            min(
                10,
                max(
                    1,
                    math.floor(4 * (n / 100) ** (2 / 9)),
                ),
            )
        )

    gamma0 = np.dot(x, x) / n

    variance = gamma0

    for lag in range(1, lags + 1):

        covariance = (
            np.dot(
                x[lag:],
                x[:-lag],
            )
            / n
        )

        weight = 1.0 - (
            lag / (lags + 1)
        )

        variance += (
            2
            * weight
            * covariance
        )

    variance /= n

    if variance <= 0:
        return 0.0

    return float(
        returns.mean()
        / np.sqrt(variance)
    )


def value_at_risk(
    returns: np.ndarray,
    alpha: float = 0.95,
) -> float:

    return float(
        np.quantile(
            returns,
            1 - alpha,
        )
    )


def conditional_var(
    returns: np.ndarray,
    alpha: float = 0.95,
) -> float:

    threshold = value_at_risk(
        returns,
        alpha,
    )

    tail = returns[
        returns <= threshold
    ]

    if len(tail) == 0:
        return threshold

    return float(tail.mean())


def metric_report(
    strategy: str,
    values: Iterable[float],
) -> MetricResult:

    x = _clean(values)

    ann_ret = annualized_return(x)
    ann_vol = float(
        x.std(ddof=1)
        * np.sqrt(252)
    )

    dd = max_drawdown(x)

    calmar = (
        ann_ret / abs(dd)
        if dd != 0
        else 0.0
    )

    return MetricResult(
        strategy=strategy,
        observations=len(x),
        total_return=float(
            np.prod(1 + x) - 1
        ),
        annualized_return=ann_ret,
        annualized_volatility=ann_vol,
        sharpe=sharpe(x),
        sortino=sortino(x),
        max_drawdown=dd,
        calmar=calmar,
        hit_rate=float(
            np.mean(x > 0)
        ),
        var_95=value_at_risk(x),
        cvar_95=conditional_var(x),
        mean_return=float(x.mean()),
        t_stat=newey_west_tstat(x),
    )


def benjamini_hochberg(
    p_values: list[float],
    q: float = 0.05,
) -> list[bool]:
    if not p_values:
        return []

    if not 0 < q <= 1:
        raise ValueError(
            "q must be between 0 and 1."
        )

    if any(
        not 0 <= p <= 1
        for p in p_values
    ):
        raise ValueError(
            "All p-values must be between 0 and 1."
        )

    indexed = sorted(
        enumerate(p_values),
        key=lambda item: item[1],
    )

    accepted = [False] * len(
        p_values
    )

    cutoff_index = -1

    total = len(p_values)

    for rank, (_, p_value) in enumerate(
        indexed,
        start=1,
    ):
        threshold = (
            rank / total
        ) * q

        if p_value <= threshold:
            cutoff_index = rank

    if cutoff_index == -1:
        return accepted

    for rank, (index, _) in enumerate(
        indexed,
        start=1,
    ):
        if rank <= cutoff_index:
            accepted[index] = True

    return accepted
