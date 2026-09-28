"""DELTA native accelerator dispatcher: Rust -> C -> C++ -> NumPy -> Python.

Zero hard dependency: every kernel has a NumPy fallback with identical
semantics (rel 1e-9 / abs 1e-12). Native DLLs are loaded via ctypes when
present; otherwise NumPy C-loops are used (already 10-50x over pandas loops).

DLLs (built by this repo, not downloaded):
  rust/target/release/delta_native.dll  (fast.rs C ABI)
  native/build/delta_fast.dll           (C kernels, -O3)
  native/build/fast_book.dll            (C++ book, -O3)
"""
from __future__ import annotations

import ctypes
import os

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_C_DLL = os.path.join(ROOT, "native", "build", "delta_fast.dll")
_CPP_DLL = os.path.join(ROOT, "native", "build", "fast_book.dll")
_RS_DLL = os.path.join(ROOT, "rust", "target", "release", "delta_native.dll")

def _try_load(path: str):
    """Load a native DLL, returning None when missing OR unloadable.

    An unloadable DLL (stale toolchain, missing CRT/python DLL) must degrade
    to the NumPy fallback, never crash the import. Backend truth is reported
    by backend(), not assumed.
    """
    if not os.path.exists(path):
        return None
    try:
        return ctypes.CDLL(path)
    except Exception:
        return None


_c = _try_load(_C_DLL)
_cpp = _try_load(_CPP_DLL)
_rs = _try_load(_RS_DLL)

if _c is not None:
    _c.delta_returns.restype = ctypes.c_size_t
    _c.delta_returns.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                 ctypes.c_void_p, ctypes.c_size_t]
    _c.delta_roll_mean_std.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_size_t,
                                       ctypes.c_void_p, ctypes.c_void_p]
    _c.delta_rsi.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_size_t, ctypes.c_void_p]
    _c.delta_ewma.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_double, ctypes.c_void_p]
    _c.delta_checksum.restype = ctypes.c_uint64
    _c.delta_checksum.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
    _c.delta_exposure.restype = ctypes.c_uint64
    _c.delta_exposure.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t]
    _c.delta_match.argtypes = [ctypes.c_uint64, ctypes.c_void_p, ctypes.c_size_t,
                               ctypes.c_void_p, ctypes.c_void_p]
    _c.delta_microprice.argtypes = [ctypes.c_double] * 4 + [ctypes.c_void_p] * 3

if _cpp is not None:
    _cpp.delta_sweep_asks.argtypes = [ctypes.c_uint64, ctypes.c_void_p, ctypes.c_void_p,
                                      ctypes.c_size_t, ctypes.c_void_p, ctypes.c_void_p,
                                      ctypes.c_void_p, ctypes.c_void_p]
    _cpp.delta_depth_stats.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t,
                                       ctypes.c_uint64, ctypes.c_void_p, ctypes.c_void_p,
                                       ctypes.c_void_p]
    _cpp.delta_impact_bps.restype = ctypes.c_double
    _cpp.delta_impact_bps.argtypes = [ctypes.c_double, ctypes.c_double, ctypes.c_double]

if _rs is not None:
    try:
        _rs.delta_roll_mean_std.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_size_t,
                                            ctypes.c_void_p, ctypes.c_void_p]
        _rs.delta_rsi_wilder.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_size_t,
                                         ctypes.c_void_p]
        _rs.delta_spearman_ic.restype = ctypes.c_double
        _rs.delta_spearman_ic.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t,
                                          ctypes.c_void_p, ctypes.c_void_p]
        _rs.delta_erc_sweep.restype = ctypes.c_double
        _rs.delta_erc_sweep.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p]
    except Exception:
        _rs = None


def backend() -> str:
    if _rs is not None:
        return "rust"
    if _c is not None:
        return "c"
    return "numpy"


# ---------- NumPy fast paths (always available, C-speed loops) ----------

def np_returns(p: np.ndarray) -> np.ndarray:
    p = np.ascontiguousarray(p, dtype=np.float64)
    b = np.abs(p[:-1])
    out = np.zeros(len(p) - 1)
    nz = b != 0
    out[nz] = (p[1:][nz] - p[:-1][nz]) / b[nz]
    return out


def roll_mean_std_pandas(x: np.ndarray, w: int, minp: int | None = None,
                         ddof: int = 0) -> tuple[np.ndarray, np.ndarray]:
    """Pandas-compatible rolling mean/std: NaN-aware, min_periods, ddof.

    Mirrors ``Series(x).rolling(w, min_periods=minp).mean()/std(ddof=ddof)``:
    windows need >= minp non-NaN values (default minp=w); NaNs are excluded
    from sum/count. Vectorized O(n) via cumsum — no pandas overhead.
    """
    x = np.ascontiguousarray(x, dtype=np.float64)
    n = len(x)
    mean = np.full(n, np.nan)
    std = np.full(n, np.nan)
    if w <= 0 or n == 0:
        return mean, std
    if minp is None:
        minp = w
    mask = ~np.isnan(x)
    # Shift-K one-pass (K = global mean): kills catastrophic cancellation in
    # s2 - s^2/cnt so z-scored features match pandas/Bottleneck to ~1e-12.
    good = x[mask]
    K = float(good.mean()) if len(good) else 0.0
    v = np.where(mask, x - K, 0.0)
    cs = np.cumsum(np.insert(v, 0, 0.0))
    cs2 = np.cumsum(np.insert(v * v, 0, 0.0))
    cc = np.cumsum(np.insert(mask.astype(np.float64), 0, 0.0))
    idx = np.arange(n)
    start = np.clip(idx + 1 - w, 0, n)
    cnt = cc[idx + 1] - cc[start]
    s = cs[idx + 1] - cs[start]
    s2 = cs2[idx + 1] - cs2[start]
    valid = cnt >= minp
    mu = np.full(n, np.nan)
    mu[valid] = s[valid] / cnt[valid] + K
    denom = np.clip(cnt - ddof, 1, None)
    var = np.full(n, np.nan)
    var[valid] = np.clip(s2[valid] - s[valid] * s[valid] / cnt[valid], 0, None) / denom[valid]
    # pandas std of a single value with ddof=1 is NaN
    var[valid & (cnt - ddof <= 0)] = np.nan
    mean = mu
    std = np.sqrt(var, out=np.full(n, np.nan), where=~np.isnan(var))
    return mean, std


def np_roll_mean_std(x: np.ndarray, w: int) -> tuple[np.ndarray, np.ndarray]:
    x = np.ascontiguousarray(x, dtype=np.float64)
    n = len(x)
    mean = np.full(n, np.nan)
    std = np.full(n, np.nan)
    if w <= 0 or n < w:
        return mean, std
    cs = np.cumsum(np.insert(x, 0, 0.0))
    cs2 = np.cumsum(np.insert(x * x, 0, 0.0))
    s = cs[w:] - cs[:-w]
    s2 = cs2[w:] - cs2[:-w]
    mu = s / w
    var = np.clip(s2 / w - mu * mu, 0, None)
    mean[w - 1:] = mu
    std[w - 1:] = np.sqrt(var)
    return mean, std


def np_rsi_wilder(px: np.ndarray, w: int = 14) -> np.ndarray:
    px = np.ascontiguousarray(px, dtype=np.float64)
    n = len(px)
    out = np.zeros(n)
    if n < 2 or w <= 0:
        return out
    d = np.diff(px, prepend=px[0])
    u = np.clip(d, 0, None)
    dn = np.clip(-d, 0, None)
    seed = min(w, n - 1)
    gu = u[1:seed + 1].sum() / w
    gd = dn[1:seed + 1].sum() / w
    for i in range(1, n):
        if i > seed:
            gu = (gu * (w - 1) + u[i]) / w
            gd = (gd * (w - 1) + dn[i]) / w
        rs = (1e12 if gu else 1.0) if gd == 0 else gu / gd
        rsi = 50.0 if i < w else 100.0 - 100.0 / (1.0 + rs)
        out[i] = rsi / 100.0 - 0.5
    return out


def np_ewma(x: np.ndarray, alpha: float) -> np.ndarray:
    x = np.ascontiguousarray(x, dtype=np.float64)
    out = np.empty_like(x)
    y = x[0]
    out[0] = y
    b = 1.0 - alpha
    for i in range(1, len(x)):
        y = alpha * x[i] + b * y
        out[i] = y
    return out


# ---------- Dispatched kernels (native when present) ----------

def returns(p: np.ndarray) -> np.ndarray:
    p = np.ascontiguousarray(p, dtype=np.float64)
    out = np.empty(max(len(p) - 1, 0), dtype=np.float64)
    if len(out) == 0:
        return out
    if _c is not None:
        _c.delta_returns(p.ctypes.data, len(p), out.ctypes.data, len(out))
        return out
    return np_returns(p)


def roll_mean_std(x: np.ndarray, w: int) -> tuple[np.ndarray, np.ndarray]:
    x = np.ascontiguousarray(x, dtype=np.float64)
    mean = np.empty(len(x), dtype=np.float64)
    std = np.empty(len(x), dtype=np.float64)
    eng = _rs or _c
    if eng is not None:
        fn = _rs.delta_roll_mean_std if _rs is not None else _c.delta_roll_mean_std
        fn(x.ctypes.data, len(x), w, mean.ctypes.data, std.ctypes.data)
        return mean, std
    return np_roll_mean_std(x, w)


def rsi(px: np.ndarray, w: int = 14) -> np.ndarray:
    px = np.ascontiguousarray(px, dtype=np.float64)
    out = np.empty(len(px), dtype=np.float64)
    if _rs is not None:
        _rs.delta_rsi_wilder(px.ctypes.data, len(px), w, out.ctypes.data)
        return out
    if _c is not None:
        _c.delta_rsi(px.ctypes.data, len(px), w, out.ctypes.data)
        return out
    return np_rsi_wilder(px, w)


def checksum_u64(v: np.ndarray) -> int:
    v = np.ascontiguousarray(v, dtype=np.uint64)
    if _c is not None:
        return int(_c.delta_checksum(v.ctypes.data, len(v)))
    return int(np.sum(v, dtype=np.uint64))


def exposure(q: np.ndarray, p: np.ndarray) -> int:
    q = np.ascontiguousarray(q, dtype=np.uint64)
    p = np.ascontiguousarray(p, dtype=np.uint64)
    if _c is not None:
        return int(_c.delta_exposure(q.ctypes.data, p.ctypes.data, len(q)))
    return int(np.sum(q * p, dtype=np.uint64))


def match_orders(buy_qty: int, asks: np.ndarray) -> tuple[int, int]:
    a = np.ascontiguousarray(asks, dtype=np.uint64)
    f = np.zeros(1, dtype=np.uint64)
    r = np.zeros(1, dtype=np.uint64)
    if _c is not None:
        _c.delta_match(int(buy_qty), a.ctypes.data, len(a), f.ctypes.data, r.ctypes.data)
        return int(f[0]), int(r[0])
    rem, fill = int(buy_qty), 0
    for q in a:
        if rem == 0:
            break
        t = min(rem, int(q))
        fill += t
        rem -= t
    return fill, rem


def sweep_asks(buy_qty: int, prices: np.ndarray, qtys: np.ndarray):
    pr = np.ascontiguousarray(prices, dtype=np.float64)
    q = np.ascontiguousarray(qtys, dtype=np.uint64)
    f = np.zeros(1, dtype=np.uint64)
    notion = np.zeros(1, dtype=np.float64)
    touched = np.zeros(1, dtype=np.uint64)
    vwap = np.zeros(1, dtype=np.float64)
    if _cpp is not None:
        _cpp.delta_sweep_asks(int(buy_qty), pr.ctypes.data, q.ctypes.data, len(q),
                              f.ctypes.data, notion.ctypes.data,
                              touched.ctypes.data, vwap.ctypes.data)
        return int(f[0]), float(notion[0]), int(touched[0]), float(vwap[0])
    # NumPy fallback: vectorized cumulative sweep
    cum = np.cumsum(q)
    full = np.searchsorted(cum, int(buy_qty), side="left")
    fill = min(int(buy_qty), int(cum[-1]) if len(cum) else 0)
    take = np.minimum(q[:full + 1], np.maximum(int(buy_qty) - np.insert(cum, 0, 0)[:full + 1], 0))
    notion_v = float((take * pr[:full + 1]).sum())
    return fill, notion_v, int(min(full + 1, len(q))), (notion_v / fill if fill else 0.0)


def spearman_ic(x: np.ndarray, y: np.ndarray) -> float:
    x = np.ascontiguousarray(x, dtype=np.float64)
    y = np.ascontiguousarray(y, dtype=np.float64)
    if _rs is not None and len(x) == len(y) and len(x) > 0:
        rx = np.empty_like(x)
        ry = np.empty_like(y)
        return float(_rs.delta_spearman_ic(x.ctypes.data, y.ctypes.data, len(x),
                                           rx.ctypes.data, ry.ctypes.data))
    import pandas as pd
    s = pd.concat([pd.Series(x), pd.Series(y)], axis=1).dropna()
    if len(s) < 3:
        return 0.0
    c = s.iloc[:, 0].corr(s.iloc[:, 1], method="spearman")
    return float(c) if c == c else 0.0


def erc_sweep(cov: np.ndarray, w: np.ndarray) -> float:
    cov = np.ascontiguousarray(cov, dtype=np.float64)
    w = np.ascontiguousarray(w, dtype=np.float64)
    n = len(w)
    if cov.shape != (n, n) or n == 0 or not np.all(np.isfinite(cov)):
        raise ValueError("erc_sweep needs a finite n x n covariance matching w.")
    if _rs is not None:
        return float(_rs.delta_erc_sweep(cov.ctypes.data, n, w.ctypes.data))
    sw = cov @ w
    pv = max(float(w @ sw), 1e-18) ** 0.5
    target = pv / n
    maxd = 0.0
    for i in range(n):
        rc = max(w[i] * sw[i] / pv, 1e-18)
        nw = w[i] * min(max((target / rc) ** 0.5, 1e-3), 1e3)
        maxd = max(maxd, abs(nw - w[i]))
        w[i] = nw
    return maxd
