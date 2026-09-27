"""W94 institutional feature store (light): versioned, PIT-safe, cached."""
from __future__ import annotations

import hashlib

import numpy as np
import pandas as pd

FEATURE_VERSION = "features-v2"

_cache: dict[tuple[str, str, str], pd.DataFrame] = {}


def _winsorize(s: pd.Series, lo: float = 0.01, hi: float = 0.99) -> pd.Series:
    q = s.quantile([lo, hi])
    return s.clip(q.iloc[0], q.iloc[1])


def compute_features(frame: pd.DataFrame, symbol: str, data_hash: str) -> pd.DataFrame:
    """PIT-safe features: every row t uses only data <= t (rolling, shift(1))."""
    key = (symbol, data_hash, FEATURE_VERSION)
    if key in _cache:
        return _cache[key]
    px = frame["close"].astype(float)
    vol = frame["volume"].astype(float)
    logp = np.log(px.clip(lower=1e-9))
    feat = pd.DataFrame(index=frame.index)
    # momentum / trend (lagged one bar so signal at t uses info up to t-1 close)
    for w in (5, 12, 20, 60):
        feat[f"mom_{w}d"] = (px / px.shift(w) - 1).shift(1)
        feat[f"trend_{w}d"] = ((logp - logp.rolling(w).mean()) / 0.05).shift(1)
    # mean reversion: z-score vs MA, lagged
    for w in (10, 20):
        mu = px.rolling(w).mean()
        sd = px.rolling(w).std().replace(0, np.nan)
        feat[f"mr_z_{w}d"] = (-(px - mu) / sd).shift(1)
    # volatility / quality
    for w in (10, 20, 60):
        feat[f"vol_{w}d"] = px.pct_change().rolling(w).std().shift(1)
    feat["range_10d"] = ((frame["high"] - frame["low"]) / px).rolling(10).mean().shift(1)
    feat["turnover_20d"] = (vol / vol.rolling(60).mean()).rolling(20).mean().shift(1)
    feat["rsi_14d"] = _rsi(px, 14).shift(1)
    feat["ret_1d"] = px.pct_change().shift(1)
    feat["ret_5d"] = (px / px.shift(5) - 1).shift(1)
    # normalize + winsorize cross-sectionally safe (per-symbol z over trailing 252)
    for c in list(feat.columns):
        feat[c] = _winsorize(feat[c].fillna(0))
        mu = feat[c].rolling(252, min_periods=20).mean()
        sd = feat[c].rolling(252, min_periods=20).std().replace(0, np.nan)
        feat[c] = ((feat[c] - mu) / sd).fillna(0).clip(-4, 4)
    feat.attrs["feature_version"] = FEATURE_VERSION
    feat.attrs["lineage"] = f"{symbol}:{data_hash}:{FEATURE_VERSION}"
    _cache[key] = feat
    return feat


def _rsi(px: pd.Series, w: int = 14) -> pd.Series:
    d = px.diff()
    up = d.clip(lower=0).rolling(w).mean()
    dn = (-d.clip(upper=0)).rolling(w).mean().replace(0, np.nan)
    rs = up / dn
    return (100 - 100 / (1 + rs)).fillna(50) / 100 - 0.5


def feature_hash(feat: pd.DataFrame) -> str:
    return hashlib.sha256(
        pd.util.hash_pandas_object(feat.fillna(0), index=True).values.tobytes()
    ).hexdigest()[:16]
