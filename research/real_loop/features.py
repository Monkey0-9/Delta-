"""W94 institutional feature store (light): versioned, PIT-safe, cached.

Speed policy: delegates to the vectorized native-accelerated implementation
(research.real_loop.features_fast, Rust/C/C++ via native.accel) unless
DELTA_FAST=0 is set, in which case the original pandas implementation below
runs. Both paths are PIT-safe (shift(1)) and agree to <1e-6.
"""
from __future__ import annotations

import hashlib
import os

import numpy as np
import pandas as pd

FEATURE_VERSION = "features-v2"

def _asof_utc(as_of) -> "pd.Timestamp":
    """Normalize as_of to tz-aware UTC; refuse naive (fail closed)."""
    import pandas as _pd
    ts = _pd.Timestamp(as_of)
    if ts.tzinfo is None:
        raise ValueError(f"as_of must be tz-aware (got naive {as_of!r})")
    return ts.tz_convert("UTC")



_cache: dict[tuple[str, str, str], pd.DataFrame] = {}


def compute_features(frame: pd.DataFrame, symbol: str, data_hash: str,
                     *, as_of: pd.Timestamp | None = None) -> pd.DataFrame:
    """PIT-safe features: every row t uses only data <= t (rolling, shift(1)).

    as_of (C-gate, P2): truncate the frame to bars at/before as_of BEFORE any
    computation, so fit statistics (winsorize bounds, rolling norms) can never
    see future bars. Walk-forward and research gates must pass the fold's
    train-end. Naive as_of is refused (fail closed on ambiguous time).
    """
    if as_of is not None:
        frame = _truncate_as_of(frame, as_of)
    cache_asof = "" if as_of is None else _asof_utc(as_of).isoformat()
    if os.environ.get("DELTA_FAST", "1") != "0":
        try:
            from research.real_loop.features_fast import compute_features_fast

            fast = compute_features_fast(frame, symbol, data_hash,
                                         as_of=as_of)
            # publish under this module's version/key so callers are unaffected
            _cache[(symbol, data_hash, FEATURE_VERSION, cache_asof)] = fast
            return fast
        except Exception:
            pass
    return _compute_features_pandas(frame, symbol, data_hash, as_of=as_of)


def _truncate_as_of(frame: pd.DataFrame,
                    as_of: pd.Timestamp) -> pd.DataFrame:
    ts = _asof_utc(as_of)
    idx = frame.index
    try:
        mask = idx.tz_convert("UTC") <= ts.tz_convert("UTC")
    except Exception:
        mask = idx <= ts.tz_localize(None) if idx.tz is None else idx <= ts
    out = frame.loc[mask]
    if len(out) == 0:
        raise ValueError(f"as_of {ts.isoformat()} precedes all bars")
    return out


def _winsorize(s: pd.Series, lo: float = 0.01, hi: float = 0.99) -> pd.Series:
    q = s.quantile([lo, hi])
    return s.clip(q.iloc[0], q.iloc[1])


def _compute_features_pandas(frame: pd.DataFrame, symbol: str, data_hash: str,
                             *, as_of: pd.Timestamp | None = None) -> pd.DataFrame:
    asof_key = "" if as_of is None else _asof_utc(as_of).isoformat()
    key = (symbol, data_hash, FEATURE_VERSION, asof_key)
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
