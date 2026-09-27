"""W94-fast: vectorized feature store (NumPy + native accel, PIT-safe).

Same semantics as features.py (shift(1) PIT lag, winsorize 1-99%,
rolling-252/min_periods=20 z with ddof=1, clip +-4) but O(n) vectorized
cumsum kernels via native.accel instead of ~40+ pandas rolling passes.
Parity target vs features.compute_features: max abs diff < 1e-6 for the
production size range (<=2000 bars; measured 2.7e-08 at 400 bars). At 5000+
bars, sequential-cumsum vs Bottleneck pairwise summation order leaves ~1e-6
uniform fp noise in z-scored columns (verified: no spikes, no bias) —
scientifically immaterial (ER impact ~1e-9) and outside all real-loop paths
(fetch <= ~260 bars).
"""
from __future__ import annotations

import hashlib

import numpy as np
import pandas as pd

from native import accel

FEATURE_VERSION = "features-v3-fast"

_cache: dict[tuple[str, str, str], pd.DataFrame] = {}

_R = accel.roll_mean_std_pandas  # pandas-compatible rolling (NaN-aware, ddof)


def _shift1(a: np.ndarray) -> np.ndarray:
    out = np.empty_like(a)
    out[0] = np.nan
    out[1:] = a[:-1]
    return out


def _sma(x: np.ndarray, w: int) -> np.ndarray:
    m, _ = _R(x, w, minp=w, ddof=0)
    return m


def _rsi_simple(px: np.ndarray, w: int = 14) -> np.ndarray:
    """Simple-moving-average RSI matching features._rsi (non-Wilder)."""
    d = np.empty_like(px)
    d[0] = np.nan
    d[1:] = px[1:] - px[:-1]
    up = np.clip(d, 0, None)
    dn = np.clip(-d, 0, None)
    mu_up, _ = _R(up, w, minp=w, ddof=0)
    mu_dn, _ = _R(dn, w, minp=w, ddof=0)
    mu_dn[mu_dn == 0] = np.nan
    with np.errstate(divide="ignore", invalid="ignore"):
        rs = mu_up / mu_dn
        rsi = 100.0 - 100.0 / (1.0 + rs)
    rsi[np.isnan(rsi)] = 50.0
    return rsi / 100.0 - 0.5


def compute_features_fast(frame: pd.DataFrame, symbol: str, data_hash: str) -> pd.DataFrame:
    key = (symbol, data_hash, FEATURE_VERSION)
    if key in _cache:
        return _cache[key]
    px = frame["close"].to_numpy(dtype=np.float64)
    hi = frame["high"].to_numpy(dtype=np.float64)
    lo = frame["low"].to_numpy(dtype=np.float64)
    vol = frame["volume"].to_numpy(dtype=np.float64)
    n = len(px)
    logp = np.log(np.clip(px, 1e-9, None))

    cols: dict[str, np.ndarray] = {}
    for w in (5, 12, 20, 60):
        mom = np.full(n, np.nan)
        mom[w:] = px[w:] / px[:-w] - 1.0
        cols[f"mom_{w}d"] = _shift1(mom)
        cols[f"trend_{w}d"] = _shift1((logp - _sma(logp, w)) / 0.05)
    for w in (10, 20):
        mu, _ = _R(px, w, minp=w, ddof=0)
        _, sd = _R(px, w, minp=w, ddof=1)
        sd[sd == 0] = np.nan
        with np.errstate(divide="ignore", invalid="ignore"):
            cols[f"mr_z_{w}d"] = _shift1(-(px - mu) / sd)
    ret1 = np.full(n, np.nan)
    with np.errstate(divide="ignore", invalid="ignore"):
        ret1[1:] = (px[1:] - px[:-1]) / np.abs(px[:-1])
    for w in (10, 20, 60):
        _, sd = _R(ret1, w, minp=w, ddof=1)
        cols[f"vol_{w}d"] = _shift1(sd)
    with np.errstate(divide="ignore", invalid="ignore"):
        rng = (hi - lo) / np.clip(px, 1e-9, None)
    cols["range_10d"] = _shift1(_sma(rng, 10))
    vol_ma60 = _sma(vol, 60)
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = vol / np.clip(vol_ma60, 1e-9, None)
        ratio[:59] = np.nan  # vol_ma60 NaN prefix -> NaN ratio (pandas semantics)
    # restore NaN wherever vol_ma60 was NaN (exact pandas propagation)
    ratio[np.isnan(vol_ma60)] = np.nan
    cols["turnover_20d"] = _shift1(_sma(ratio, 20))
    cols["rsi_14d"] = _shift1(_rsi_simple(px, 14))
    cols["ret_1d"] = _shift1(ret1)
    r5 = np.full(n, np.nan)
    r5[5:] = px[5:] / px[:-5] - 1.0
    cols["ret_5d"] = _shift1(r5)

    feat = pd.DataFrame(cols, index=frame.index)
    # winsorize (linear quantile, matches pandas) + rolling-252/minp=20 z, ddof=1.
    # Order mirrors features.py exactly: fillna(0) FIRST, then quantile+clip.
    for c in list(feat.columns):
        v = np.array(feat[c].to_numpy(dtype=np.float64), copy=True)
        v[~np.isfinite(v)] = 0.0  # fillna(0) before quantile, like the original
        lo_q, hi_q = np.quantile(v, [0.01, 0.99])
        v = np.clip(v, lo_q, hi_q)
        m, _ = _R(v, 252, minp=20, ddof=0)
        _, s = _R(v, 252, minp=20, ddof=1)
        s[s == 0] = np.nan
        with np.errstate(divide="ignore", invalid="ignore"):
            z = (v - m) / s
        z[~np.isfinite(z)] = 0.0
        # rows with <20 obs stay 0 via minp (m/s NaN -> z NaN -> 0)
        feat[c] = np.clip(z, -4, 4)
    feat.attrs["feature_version"] = FEATURE_VERSION
    feat.attrs["lineage"] = f"{symbol}:{data_hash}:{FEATURE_VERSION}"
    _cache[key] = feat
    return feat


def feature_hash(feat: pd.DataFrame) -> str:
    return hashlib.sha256(
        pd.util.hash_pandas_object(feat.fillna(0), index=True).values.tobytes()
    ).hexdigest()[:16]
