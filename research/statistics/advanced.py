from __future__ import annotations

from dataclasses import dataclass
import math
from statistics import NormalDist
from typing import Sequence


@dataclass(frozen=True, slots=True)
class PerformanceReport:

    observations: int
    mean: float
    volatility: float
    sharpe: float
    sortino: float
    max_drawdown: float
    hit_rate: float
    skew: float
    excess_kurtosis: float


def _clean(
    values: Sequence[float],
) -> list[float]:

    result = [
        float(value)
        for value in values
        if math.isfinite(
            float(value)
        )
    ]

    if len(result) < 2:
        raise ValueError(
            "at least two finite observations required"
        )

    return result


def mean(
    values: Sequence[float],
) -> float:

    values = _clean(values)

    return sum(values) / len(values)


def volatility(
    values: Sequence[float],
    annualization: float = 1.0,
) -> float:

    values = _clean(values)

    m = sum(values) / len(values)

    variance = sum(
        (value - m) ** 2
        for value in values
    ) / (len(values) - 1)

    return math.sqrt(
        variance * annualization
    )


def sharpe(
    values: Sequence[float],
    annualization: float = 1.0,
) -> float:

    sd = volatility(
        values,
        annualization,
    )

    if sd == 0:
        return 0.0

    return (
        mean(values)
        * math.sqrt(annualization)
        / sd
    )


def sortino(
    values: Sequence[float],
    target: float = 0.0,
    annualization: float = 1.0,
) -> float:

    values = _clean(values)

    downside = [
        min(0.0, value - target) ** 2
        for value in values
    ]

    denominator = math.sqrt(
        sum(downside)
        / max(1, len(values) - 1)
    )

    if denominator == 0:
        return 0.0

    return (
        (mean(values) - target)
        * math.sqrt(annualization)
        / denominator
    )


def max_drawdown(
    values: Sequence[float],
) -> float:

    values = _clean(values)

    wealth = 1.0
    peak = 1.0
    worst = 0.0

    for value in values:

        wealth *= 1.0 + value

        peak = max(
            peak,
            wealth,
        )

        drawdown = (
            wealth / peak - 1.0
        )

        worst = min(
            worst,
            drawdown,
        )

    return worst


def _moments(
    values: Sequence[float],
):

    values = _clean(values)

    n = len(values)

    m = sum(values) / n

    m2 = sum(
        (value - m) ** 2
        for value in values
    ) / n

    if m2 == 0:
        return 0.0, 0.0

    m3 = sum(
        (value - m) ** 3
        for value in values
    ) / n

    m4 = sum(
        (value - m) ** 4
        for value in values
    ) / n

    skew = (
        m3 / m2 ** 1.5
    )

    kurtosis = (
        m4 / m2 ** 2
        - 3.0
    )

    return skew, kurtosis


def report(
    values: Sequence[float],
    annualization: float = 1.0,
) -> PerformanceReport:

    values = _clean(values)

    skew, kurtosis = _moments(
        values
    )

    return PerformanceReport(
        observations=len(values),
        mean=mean(values),
        volatility=volatility(
            values,
            annualization,
        ),
        sharpe=sharpe(
            values,
            annualization,
        ),
        sortino=sortino(
            values,
            0.0,
            annualization,
        ),
        max_drawdown=max_drawdown(
            values
        ),
        hit_rate=sum(
            value > 0
            for value in values
        ) / len(values),
        skew=skew,
        excess_kurtosis=kurtosis,
    )


def newey_west_mean_tstat(
    values: Sequence[float],
    lags: int | None = None,
) -> float:

    values = _clean(values)

    n = len(values)

    if lags is None:
        lags = max(
            1,
            int(
                4 * (n / 100) ** (2 / 9)
            ),
        )

    mu = sum(values) / n

    gamma0 = sum(
        (value - mu) ** 2
        for value in values
    ) / n

    variance = gamma0

    for k in range(
        1,
        min(lags, n - 1) + 1,
    ):

        gamma = sum(
            (
                values[t] - mu
            )
            * (
                values[t-k] - mu
            )
            for t in range(k, n)
        ) / n

        weight = (
            1.0
            - k / (lags + 1)
        )

        variance += (
            2.0
            * weight
            * gamma
        )

    standard_error = math.sqrt(
        max(
            variance,
            1e-30,
        ) / n
    )

    return mu / standard_error


def bootstrap_mean_ci(
    values: Sequence[float],
    *,
    seed: int = 7,
    samples: int = 5000,
    alpha: float = 0.05,
):

    import random

    values = _clean(values)

    rng = random.Random(seed)

    means = []

    for _ in range(samples):

        sample = [
            rng.choice(values)
            for _ in values
        ]

        means.append(
            sum(sample)
            / len(sample)
        )

    means.sort()

    low_index = int(
        alpha / 2 * samples
    )

    high_index = int(
        (1 - alpha / 2)
        * samples
    ) - 1

    return (
        means[low_index],
        means[high_index],
    )


def benjamini_hochberg(
    pvalues: Sequence[float],
) -> list[float]:

    n = len(pvalues)

    if n == 0:
        return []

    indexed = sorted(
        enumerate(
            float(p)
            for p in pvalues
        ),
        key=lambda item: item[1],
    )

    qvalues = [1.0] * n

    running = 1.0

    for rank in range(n, 0, -1):

        index, pvalue = (
            indexed[rank - 1]
        )

        running = min(
            running,
            pvalue * n / rank,
        )

        qvalues[index] = min(
            1.0,
            running,
        )

    return qvalues


def probabilistic_sharpe_ratio(
    observed_sharpe: float,
    benchmark_sharpe: float,
    n: int,
    skew: float = 0.0,
    excess_kurtosis: float = 0.0,
) -> float:

    if n < 2:
        raise ValueError(
            "n must be >= 2"
        )

    denominator = math.sqrt(
        max(
            1e-12,
            (
                1.0
                - skew * observed_sharpe
                + (
                    (excess_kurtosis + 3.0)
                    / 4.0
                )
                * observed_sharpe**2
            )
            / (n - 1),
        )
    )

    z = (
        observed_sharpe
        - benchmark_sharpe
    ) / denominator

    return NormalDist().cdf(z)