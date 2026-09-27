from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class Factor:
    name: str
    values: pd.Series


def zscore(
    series: pd.Series,
) -> pd.Series:

    mean = series.mean()
    std = series.std(ddof=0)

    if not np.isfinite(std) or std <= 1e-12:
        return pd.Series(
            0.0,
            index=series.index,
        )

    return (
        (series - mean) / std
    ).replace(
        [np.inf, -np.inf],
        np.nan,
    ).fillna(0.0)


def momentum(
    close: pd.Series,
    lookback: int = 20,
) -> Factor:

    value = close.pct_change(
        lookback
    )

    return Factor(
        "momentum",
        zscore(value),
    )


def trend(
    close: pd.Series,
    fast: int = 20,
    slow: int = 100,
) -> Factor:

    fast_ma = close.rolling(
        fast
    ).mean()

    slow_ma = close.rolling(
        slow
    ).mean()

    value = fast_ma / slow_ma - 1.0

    return Factor(
        "trend",
        zscore(value),
    )


def mean_reversion(
    close: pd.Series,
    window: int = 20,
) -> Factor:

    mean = close.rolling(
        window
    ).mean()

    std = close.rolling(
        window
    ).std()

    z = (
        (close - mean)
        / std.replace(0.0, np.nan)
    )

    return Factor(
        "mean_reversion",
        -z.fillna(0.0),
    )


def realized_volatility(
    returns: pd.Series,
    window: int = 20,
) -> Factor:

    value = (
        returns.rolling(window)
        .std()
        * np.sqrt(252)
    )

    return Factor(
        "realized_volatility",
        value.fillna(0.0),
    )


def downside_volatility(
    returns: pd.Series,
    window: int = 20,
) -> Factor:

    downside = returns.clip(
        upper=0.0
    )

    value = (
        downside.pow(2)
        .rolling(window)
        .mean()
        .pow(0.5)
        * np.sqrt(252)
    )

    return Factor(
        "downside_volatility",
        value.fillna(0.0),
    )


def skewness(
    returns: pd.Series,
    window: int = 60,
) -> Factor:

    return Factor(
        "skewness",
        returns.rolling(window)
        .skew()
        .fillna(0.0),
    )


def kurtosis(
    returns: pd.Series,
    window: int = 60,
) -> Factor:

    return Factor(
        "kurtosis",
        returns.rolling(window)
        .kurt()
        .fillna(0.0),
    )


def beta(
    asset_returns: pd.Series,
    market_returns: pd.Series,
    window: int = 60,
) -> Factor:

    covariance = (
        asset_returns
        .rolling(window)
        .cov(market_returns)
    )

    market_variance = (
        market_returns
        .rolling(window)
        .var()
    )

    value = (
        covariance
        / market_variance.replace(
            0.0,
            np.nan,
        )
    )

    return Factor(
        "beta",
        value.fillna(0.0),
    )