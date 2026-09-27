from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class BacktestConfig:
    lookback: int = 20
    rebalance_cost_bps: float = 2.0
    annualization: int = 252


def prices_to_returns(
    prices: pd.DataFrame,
) -> pd.DataFrame:

    prices = prices.copy()

    prices["date"] = pd.to_datetime(
        prices["date"],
        utc=True,
    )

    wide = prices.pivot(
        index="date",
        columns="asset",
        values="close",
    ).sort_index()

    return wide.pct_change()


def _safe_normalize(weights: pd.DataFrame) -> pd.DataFrame:
    denom = weights.abs().sum(axis=1)

    return weights.div(
        denom.replace(0, np.nan),
        axis=0,
    ).fillna(0.0)


def equal_weight(
    returns: pd.DataFrame,
) -> pd.Series:

    weights = pd.DataFrame(
        1.0,
        index=returns.index,
        columns=returns.columns,
    )

    weights = _safe_normalize(weights)

    return (
        weights.shift(1).fillna(0)
        * returns
    ).sum(axis=1)


def momentum(
    returns: pd.DataFrame,
    lookback: int = 20,
) -> pd.Series:

    signal = returns.rolling(
        lookback
    ).sum().shift(1)

    weights = np.sign(signal)

    weights = _safe_normalize(weights)

    return (
        weights * returns
    ).sum(axis=1)


def mean_reversion(
    returns: pd.DataFrame,
    lookback: int = 20,
) -> pd.Series:

    signal = -returns.rolling(
        lookback
    ).sum().shift(1)

    weights = np.sign(signal)

    weights = _safe_normalize(weights)

    return (
        weights * returns
    ).sum(axis=1)


def volatility_target(
    returns: pd.DataFrame,
    target_vol: float = 0.10,
    lookback: int = 20,
) -> pd.Series:

    base = equal_weight(returns)

    realized = (
        base.rolling(lookback)
        .std()
        * np.sqrt(252)
    )

    leverage = (
        target_vol
        / realized.replace(0, np.nan)
    ).clip(
        lower=0,
        upper=3,
    )

    return (
        base * leverage.shift(1)
    ).fillna(0.0)


def apply_turnover_cost(
    strategy_returns: pd.Series,
    weights: pd.DataFrame,
    cost_bps: float,
) -> pd.Series:

    turnover = weights.diff().abs().sum(axis=1)

    cost = turnover * (
        cost_bps / 10_000
    )

    return (
        strategy_returns - cost
    ).fillna(0.0)


def run_baselines(
    prices: pd.DataFrame,
    config: BacktestConfig | None = None,
) -> pd.DataFrame:

    config = config or BacktestConfig()

    returns = prices_to_returns(prices)

    output = pd.DataFrame(index=returns.index)

    output["equal_weight"] = equal_weight(
        returns
    )

    output["momentum"] = momentum(
        returns,
        config.lookback,
    )

    output["mean_reversion"] = mean_reversion(
        returns,
        config.lookback,
    )

    output["volatility_target"] = volatility_target(
        returns,
        lookback=config.lookback,
    )

    return output.dropna(how="all")
