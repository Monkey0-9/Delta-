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


# --- 16-class institutional extension (price/volume-only; fundamentals refuse without PIT) ---
def value_earnings_yield(close: pd.Series, eps_ttm: pd.Series) -> Factor:
    """VALUE: earnings yield E/P (higher = cheaper). Requires PIT eps."""
    return Factor("value_earnings_yield", zscore((eps_ttm / close.replace(0.0, np.nan)).fillna(0.0)))


def quality_roe(roe: pd.Series) -> Factor:
    """QUALITY: return on equity, z-scored."""
    return Factor("quality_roe", zscore(roe.fillna(0.0)))


def size_log_market_cap(market_cap: pd.Series) -> Factor:
    """SIZE: -log(market cap) so small-cap tilts positive (Fama-French SMB direction)."""
    import numpy as _np
    v = -_np.log(market_cap.replace(0.0, _np.nan).fillna(market_cap.median() or 1.0))
    return Factor("size", zscore(v.fillna(0.0)))


def low_volatility(returns: pd.Series, window: int = 60) -> Factor:
    """LOW VOL: negative realized vol (low-vol anomaly long leg)."""
    rv = returns.rolling(window).std() * (252 ** 0.5)
    return Factor("low_volatility", zscore((-rv.fillna(0.0))))


def profitability_gross_margin(gross_margin: pd.Series) -> Factor:
    """PROFITABILITY: gross margin, z-scored (Novy-Marx direction)."""
    return Factor("profitability", zscore(gross_margin.fillna(0.0)))


def investment_asset_growth(asset_growth: pd.Series) -> Factor:
    """INVESTMENT: negative asset growth (conservative-minus-aggressive)."""
    return Factor("investment", zscore((-asset_growth.fillna(0.0))))


def short_reversal(close: pd.Series, window: int = 5) -> Factor:
    """REVERSAL: negative prior-week return (Jegadeesh short-term reversal)."""
    return Factor("short_reversal", zscore((-close.pct_change(window).fillna(0.0))))


def liquidity_amihud(returns: pd.Series, dollar_vol: pd.Series, window: int = 20) -> Factor:
    """LIQUIDITY: negative Amihud illiquidity mean (liquid-minus-illiquid)."""
    illiq = (returns.abs() / dollar_vol.replace(0.0, float("nan"))).rolling(window).mean()
    return Factor("liquidity", zscore((-illiq.fillna(illiq.median() or 0.0))))


def carry_term_structure(near: pd.Series, far: pd.Series) -> Factor:
    """CARRY/TERM: (near-far)/far roll yield proxy for futures/curves."""
    v = ((near - far) / far.replace(0.0, float("nan"))).fillna(0.0)
    return Factor("carry", zscore(v))


def volatility_breakout(close: pd.Series, window: int = 20, k: float = 1.5) -> Factor:
    """VOLATILITY/BREAKOUT: distance above rolling high in vol units."""
    hi = close.rolling(window).max()
    vol = close.pct_change().rolling(window).std().replace(0.0, float("nan"))
    v = ((close - hi) / (close * vol)).fillna(0.0)
    return Factor("volatility_breakout", zscore(v))


def microstructure_rsi2(close: pd.Series, window: int = 2) -> Factor:
    """MICROSTRUCTURE: short-window RSI (Connors RSI-2 mean-reversion)."""
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0).rolling(window).mean()
    loss = (-delta.where(delta < 0, 0.0)).rolling(window).mean()
    rs = gain / loss.replace(0.0, float("nan"))
    rsi = (100 - 100 / (1 + rs)).fillna(50.0) - 50.0
    return Factor("microstructure_rsi2", zscore(rsi))


def event_gap(close: pd.Series, prev_close: pd.Series) -> Factor:
    """EVENT: overnight gap z-score (earnings/gap drift proxy)."""
    gap = ((close - prev_close) / prev_close.replace(0.0, float("nan"))).fillna(0.0)
    return Factor("event_gap", zscore(gap))


FACTOR_REGISTRY = ("momentum", "trend", "mean_reversion", "realized_volatility",
                   "downside_volatility", "skewness", "kurtosis", "beta",
                   "value_earnings_yield", "quality_roe", "size", "low_volatility",
                   "profitability", "investment", "short_reversal", "liquidity",
                   "carry", "volatility_breakout", "microstructure_rsi2", "event_gap")