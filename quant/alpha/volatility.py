"""Volatility alpha family: low-vol tilt + vol-regime timing (real math).

Features from daily OHLCV only (no IV feed exists; no IV is fabricated —
iv_rv_spread is documented unavailable until an options feed lands):
- realized_vol_20d: rolling std of log returns, annualized.
- vol_percentile_252d: current vol rank over 1y (0..1).
- vol_of_vol_20d: std of daily vol changes.
- vol_regime_z: (vol20 - mean(vol60)) / std(vol60).

Signal in [-1,1]: long low-vol (negative vol percentile deviation), flattened
when vol regime is extreme (|z| > 3, untradeable dislocation). Shifted by 2
bars like the rest of the research path (no lookahead).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

FAMILY = "volatility"
FEATURE_VERSION = "volatility-v1"


def compute(frame: pd.DataFrame) -> pd.DataFrame:
    close = frame["close"].astype(float)
    logret = np.log(close / close.shift(1))
    rv20 = logret.rolling(20).std() * np.sqrt(252)
    rv60 = logret.rolling(60).std() * np.sqrt(252)
    out = pd.DataFrame(index=frame.index)
    out["realized_vol"] = rv20
    out["vol_percentile_252d"] = rv20.rolling(252).rank(pct=True)
    out["vol_of_vol"] = rv20.diff().rolling(20).std()
    mu = rv60.rolling(60).mean()
    sd = rv60.rolling(60).std()
    out["vol_regime_z"] = (rv20 - mu) / sd.replace(0, np.nan)
    return out


def signal(features: pd.DataFrame) -> pd.Series:
    tilt = -((features["vol_percentile_252d"].fillna(0.5) - 0.5) * 2.0)
    extreme = features["vol_regime_z"].abs() > 3.0
    sig = tilt.mask(extreme.fillna(False), 0.0)
    return sig.shift(2).fillna(0).clip(-1, 1)
