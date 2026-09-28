"""Liquidity alpha family: Amihud + turnover + spread proxy (real math).

Features from daily OHLCV only:
- amihud_20d: mean(|ret| / dollar_volume), the Amihud illiquidity ratio.
- turnover_z_20d: volume z-score vs 60d (abnormal activity).
- spread_proxy: (high - low) / close, a daily spread estimator.
- illiquidity: cross-sectional-free composite = z(amihud) + z(spread) - z(turnover).

Signal in [-1,1]: illiquidity premium is long-illiquid BUT capacity-binds
first — capacity_flag() reports the capital at which estimated participation
exceeds 10% ADV so sizing respects the bind. Signal itself is long-liquid
tilt (negative illiquidity z) for tradeability; premium capture is sized,
not assumed.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

FAMILY = "liquidity"
FEATURE_VERSION = "liquidity-v1"
PARTICIPATION_CAP = 0.10


def compute(frame: pd.DataFrame) -> pd.DataFrame:
    close = frame["close"].astype(float)
    ret = close.pct_change().abs()
    dollar_vol = (close * frame["volume"].astype(float)).replace(0, np.nan)
    out = pd.DataFrame(index=frame.index)
    out["amihud"] = (ret / dollar_vol).rolling(20).mean()
    vol = frame["volume"].astype(float)
    out["turnover_z"] = (vol - vol.rolling(60).mean()) / vol.rolling(60).std().replace(0, np.nan)
    out["spread_proxy"] = ((frame["high"] - frame["low"]) / close).rolling(20).mean()
    for c in ("amihud", "spread_proxy"):
        mu, sd = out[c].rolling(60).mean(), out[c].rolling(60).std().replace(0, np.nan)
        out[f"{c}_z"] = (out[c] - mu) / sd
    out["illiquidity"] = (out["amihud_z"].fillna(0) + out["spread_proxy_z"].fillna(0)
                          - out["turnover_z"].fillna(0)) / 3.0
    out["adv_20d"] = dollar_vol.rolling(20).mean()
    return out


def signal(features: pd.DataFrame) -> pd.Series:
    sig = -(features["illiquidity"].fillna(0)).clip(-1, 1)
    return sig.shift(2).fillna(0)


def capacity_flag(features: pd.DataFrame, capital: float, price: float,
                  turnover: float = 1.0) -> dict:
    """Capital level vs 10% ADV bind. Returns participation + binds flag."""
    adv = float(features["adv_20d"].dropna().iloc[-1]) if len(features.dropna()) else 0.0
    if adv <= 0 or price <= 0 or capital <= 0:
        raise ValueError("adv, price and capital must be positive.")
    part = (capital * turnover / price) / (adv / price)
    return {"capital": capital, "participation": part,
            "binds": bool(part > PARTICIPATION_CAP), "cap": PARTICIPATION_CAP}
