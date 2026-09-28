"""Statistical-arbitrage family: pair spread + OU half-life (real math, numpy only).

Two-step Engle-Granger style: OLS hedge ratio of y on x over a lookback,
spread = y - beta*x, OU regression d(spread) = a + b*spread + e gives
half-life = -ln(2)/b. Signal = -z(spread) gated on 5d < half-life < 250d
(non-stationary or never-reverting spreads are rejected, not traded).
Single-pair interface; basket use = caller iterates pairs.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

FAMILY = "stat_arb"
FEATURE_VERSION = "stat-arb-v1"
MIN_HALF_LIFE = 5.0
MAX_HALF_LIFE = 250.0


def hedge_ratio(y: pd.Series, x: pd.Series, lookback: int = 60) -> pd.Series:
    """Rolling OLS beta of y on x (with intercept)."""
    beta = pd.Series(np.nan, index=y.index)
    yv, xv = y.values.astype(float), x.values.astype(float)
    for i in range(lookback, len(y)):
        yw, xw = yv[i - lookback:i], xv[i - lookback:i]
        if not (np.all(np.isfinite(yw)) and np.all(np.isfinite(xw))):
            continue
        a = np.vstack([xw, np.ones_like(xw)]).T
        try:
            b, *_ = np.linalg.lstsq(a, yw, rcond=None)
        except Exception:
            continue
        beta.iloc[i] = b[0]
    return beta


def half_life(spread: pd.Series, lookback: int = 60) -> pd.Series:
    """OU half-life per bar over trailing window; NaN where non-reverting."""
    hl = pd.Series(np.nan, index=spread.index)
    sv = spread.values.astype(float)
    for i in range(lookback, len(spread)):
        w = sv[i - lookback:i]
        if not np.all(np.isfinite(w)):
            continue
        dw = np.diff(w)
        lag = w[:-1]
        a = np.vstack([lag, np.ones_like(lag)]).T
        try:
            b, *_ = np.linalg.lstsq(a, dw, rcond=None)
        except Exception:
            continue
        if b[0] < 0:
            hl.iloc[i] = -np.log(2.0) / b[0]
    return hl


def compute(y: pd.Series, x: pd.Series, lookback: int = 60) -> pd.DataFrame:
    beta = hedge_ratio(y, x, lookback)
    spread = y - beta * x
    hl = half_life(spread, lookback)
    z = (spread - spread.rolling(lookback).mean()) / spread.rolling(lookback).std().replace(0, np.nan)
    return pd.DataFrame({"hedge_ratio": beta, "spread": spread,
                         "half_life": hl, "spread_z": z})


def signal(features: pd.DataFrame) -> pd.Series:
    ok = (features["half_life"] > MIN_HALF_LIFE) & (features["half_life"] < MAX_HALF_LIFE)
    sig = (-features["spread_z"].fillna(0)).clip(-2, 2) / 2.0
    sig = sig.mask(~ok.fillna(False), 0.0)
    return sig.shift(2).fillna(0).clip(-1, 1)
