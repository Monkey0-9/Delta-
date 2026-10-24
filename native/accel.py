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
import math
import os

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _try_load(path: str):
    """Load a native DLL/SO, returning None when missing OR unloadable.

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


def _find_library(candidates: list[str]) -> tuple[ctypes.CDLL | None, str]:
    for path in candidates:
        lib = _try_load(path)
        if lib is not None:
            return lib, path
    return None, candidates[0] if candidates else ""


_c, _C_DLL = _find_library([
    os.path.join(ROOT, "native", "build", "delta_fast.so"),
    os.path.join(ROOT, "native", "build", "delta_fast.dll"),
    os.path.join(ROOT, "native", "build", "libdelta_fast.so"),
    os.path.join(ROOT, "native", "build", "libdelta_fast.dylib"),
])

_cpp, _CPP_DLL = _find_library([
    os.path.join(ROOT, "native", "build", "fast_book.so"),
    os.path.join(ROOT, "native", "build", "fast_book.dll"),
    os.path.join(ROOT, "native", "build", "libfast_book.so"),
    os.path.join(ROOT, "native", "build", "libfast_book.dylib"),
])

_rs, _RS_DLL = _find_library([
    os.path.join(ROOT, "target", "release", "libdelta_native.so"),
    os.path.join(ROOT, "target", "release", "delta_native.dll"),
    os.path.join(ROOT, "target", "release", "libdelta_native.dylib"),
    os.path.join(ROOT, "rust", "target", "release", "libdelta_native.so"),
    os.path.join(ROOT, "rust", "target", "release", "delta_native.dll"),
    os.path.join(ROOT, "rust", "target", "release", "libdelta_native.dylib"),
])

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
        if hasattr(_rs, "delta_simplex_cap"):
            _rs.delta_simplex_cap.restype = ctypes.c_int32
            _rs.delta_simplex_cap.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_double]
        if hasattr(_rs, "delta_black_scholes_greeks"):
            _rs.delta_black_scholes_greeks.restype = ctypes.c_int32
            _rs.delta_black_scholes_greeks.argtypes = [
                ctypes.c_double, ctypes.c_double, ctypes.c_double,
                ctypes.c_double, ctypes.c_double, ctypes.c_int32, ctypes.c_void_p,
            ]
        if hasattr(_rs, "delta_var_cvar"):
            _rs.delta_var_cvar.restype = ctypes.c_int32
            _rs.delta_var_cvar.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_double, ctypes.c_void_p]
        if hasattr(_rs, "delta_vwap_bands"):
            _rs.delta_vwap_bands.argtypes = [
                ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t,
                ctypes.c_void_p, ctypes.c_void_p,
            ]
        if hasattr(_rs, "delta_macd"):
            _rs.delta_macd.argtypes = [
                ctypes.c_void_p, ctypes.c_size_t, ctypes.c_size_t,
                ctypes.c_size_t, ctypes.c_size_t,
                ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
            ]
        if hasattr(_rs, "delta_ncm_similarity"):
            _rs.delta_ncm_similarity.argtypes = [
                ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_size_t, ctypes.c_void_p
            ]
        if hasattr(_rs, "delta_ncm_entropy"):
            _rs.delta_ncm_entropy.restype = ctypes.c_double
            _rs.delta_ncm_entropy.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
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


def simplex_cap(w: np.ndarray, max_weight: float) -> np.ndarray:
    """Project weights onto bounded simplex {w in [0, max_weight]^n : sum(w) = 1}.

    Uses exact iterative water-filling, eliminating weight re-inflation.
    Accelerated via native Rust kernel with Python/NumPy fallback.
    """
    w_arr = np.clip(np.asarray(w, dtype=np.float64), 0.0, None).copy()
    n = len(w_arr)
    if n == 0:
        return w_arr
    if n * max_weight < 1.0 - 1e-9:
        raise ValueError(
            f"Infeasible weight cap: {n} assets with max_weight={max_weight:.4f} "
            f"cannot sum to 1.0 (maximum feasible sum is {n * max_weight:.4f})"
        )
    if _rs is not None and hasattr(_rs, "delta_simplex_cap"):
        w_c = np.ascontiguousarray(w_arr, dtype=np.float64)
        ret = int(_rs.delta_simplex_cap(w_c.ctypes.data, n, float(max_weight)))
        if ret == 0:
            return w_c

    # Python/NumPy fallback
    if w_arr.sum() == 0:
        w_arr = np.ones(n, dtype=np.float64) / n
    else:
        w_arr = w_arr / w_arr.sum()

    fixed = np.zeros(n, dtype=bool)
    for _ in range(n + 1):
        violators = (~fixed) & (w_arr > max_weight + 1e-12)
        if not np.any(violators):
            break
        fixed |= violators
        w_arr[fixed] = max_weight
        rem_sum = 1.0 - float(fixed.sum()) * max_weight
        free = ~fixed
        if np.any(free):
            free_sum = float(w_arr[free].sum())
            if free_sum > 1e-15:
                w_arr[free] *= rem_sum / free_sum
            else:
                w_arr[free] = rem_sum / float(free.sum())
    return np.clip(w_arr, 0.0, max_weight)


def black_scholes(
    spot: float,
    strike: float,
    expiry_years: float,
    vol: float,
    risk_free: float = 0.05,
    is_call: bool = True,
) -> dict[str, float]:
    """Calculate European option price and analytical Greeks.

    Accelerated via native Rust kernel with pure Python fallback.
    """
    import math

    if spot <= 0.0 or strike <= 0.0 or expiry_years <= 0.0 or vol <= 0.0:
        return {
            "price": 0.0,
            "delta": 0.0,
            "gamma": 0.0,
            "vega": 0.0,
            "theta": 0.0,
            "rho": 0.0,
        }

    if _rs is not None and hasattr(_rs, "delta_black_scholes_greeks"):
        out = np.zeros(6, dtype=np.float64)
        ret = _rs.delta_black_scholes_greeks(
            float(spot), float(strike), float(expiry_years),
            float(vol), float(risk_free), 1 if is_call else 0,
            out.ctypes.data,
        )
        if ret == 1:
            return {
                "price": float(out[0]),
                "delta": float(out[1]),
                "gamma": float(out[2]),
                "vega": float(out[3]),
                "theta": float(out[4]),
                "rho": float(out[5]),
            }

    # Python analytical fallback
    sqrt_t = math.sqrt(expiry_years)
    d1 = (math.log(spot / strike) + (risk_free + 0.5 * vol * vol) * expiry_years) / (vol * sqrt_t)
    d2 = d1 - vol * sqrt_t

    def norm_cdf(x: float) -> float:
        return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

    def norm_pdf(x: float) -> float:
        return (1.0 / math.sqrt(2.0 * math.pi)) * math.exp(-0.5 * x * x)

    nd1 = norm_cdf(d1)
    nd2 = norm_cdf(d2)
    pdf_d1 = norm_pdf(d1)
    disc = math.exp(-risk_free * expiry_years)

    if is_call:
        price = spot * nd1 - strike * disc * nd2
        delta = nd1
        theta = -(spot * pdf_d1 * vol) / (2.0 * sqrt_t) - risk_free * strike * disc * nd2
        rho = strike * expiry_years * disc * nd2 / 100.0
    else:
        price = strike * disc * norm_cdf(-d2) - spot * norm_cdf(-d1)
        delta = nd1 - 1.0
        theta = -(spot * pdf_d1 * vol) / (2.0 * sqrt_t) + risk_free * strike * disc * norm_cdf(-d2)
        rho = -strike * expiry_years * disc * norm_cdf(-d2) / 100.0

    gamma = pdf_d1 / (spot * vol * sqrt_t)
    vega = (spot * sqrt_t * pdf_d1) / 100.0
    theta /= 365.0

    return {
        "price": max(0.0, price),
        "delta": delta,
        "gamma": gamma,
        "vega": vega,
        "theta": theta,
        "rho": rho,
    }


def var_cvar(returns: np.ndarray, alpha: float = 0.05) -> tuple[float, float]:
    """Calculate historical Value at Risk (VaR) and Conditional VaR (Expected Shortfall).

    Accelerated via native Rust kernel with NumPy fallback.
    Returns (var, cvar) where positive values represent losses.
    """
    arr = np.ascontiguousarray(returns, dtype=np.float64)
    if len(arr) < 5:
        return 0.0, 0.0
    if _rs is not None and hasattr(_rs, "delta_var_cvar"):
        out = np.zeros(2, dtype=np.float64)
        ret = _rs.delta_var_cvar(arr.ctypes.data, len(arr), float(alpha), out.ctypes.data)
        if ret == 1:
            return float(out[0]), float(out[1])

    # NumPy fallback
    sorted_r = np.sort(arr)
    cutoff = max(1, min(len(sorted_r) - 1, int(math.floor(len(sorted_r) * alpha))))
    var = max(0.0, float(-sorted_r[cutoff - 1]))
    cvar = max(var, float(-sorted_r[:cutoff].mean()))
    return var, cvar


def vwap_bands(prices: np.ndarray, volumes: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Calculate cumulative Volume-Weighted Average Price and rolling standard deviation.

    Accelerated via native Rust kernel with NumPy fallback.
    """
    p = np.ascontiguousarray(prices, dtype=np.float64)
    v = np.ascontiguousarray(volumes, dtype=np.float64)
    n = min(len(p), len(v))
    if n == 0:
        return np.empty(0, dtype=np.float64), np.empty(0, dtype=np.float64)

    if _rs is not None and hasattr(_rs, "delta_vwap_bands"):
        out_vwap = np.empty(n, dtype=np.float64)
        out_std = np.empty(n, dtype=np.float64)
        _rs.delta_vwap_bands(p.ctypes.data, v.ctypes.data, n, out_vwap.ctypes.data, out_std.ctypes.data)
        return out_vwap, out_std

    cum_v = np.cumsum(np.clip(v, 0.0, None))
    cum_pv = np.cumsum(p * np.clip(v, 0.0, None))
    cum_pv2 = np.cumsum(p * p * np.clip(v, 0.0, None))
    valid = cum_v > 0
    vwap = np.where(valid, cum_pv / np.maximum(cum_v, 1e-12), p)
    var = np.clip(np.where(valid, cum_pv2 / np.maximum(cum_v, 1e-12) - vwap * vwap, 0.0), 0.0, None)
    return vwap, np.sqrt(var)


def macd(
    prices: np.ndarray,
    fast_p: int = 12,
    slow_p: int = 26,
    signal_p: int = 9,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Calculate single-pass Moving Average Convergence Divergence.

    Accelerated via native Rust kernel with NumPy fallback.
    Returns (macd_line, signal_line, histogram).
    """
    p = np.ascontiguousarray(prices, dtype=np.float64)
    n = len(p)
    if n == 0:
        return (np.empty(0), np.empty(0), np.empty(0))

    if _rs is not None and hasattr(_rs, "delta_macd"):
        out_macd = np.empty(n, dtype=np.float64)
        out_sig = np.empty(n, dtype=np.float64)
        out_hist = np.empty(n, dtype=np.float64)
        _rs.delta_macd(
            p.ctypes.data, n, fast_p, slow_p, signal_p,
            out_macd.ctypes.data, out_sig.ctypes.data, out_hist.ctypes.data,
        )
        return out_macd, out_sig, out_hist

    k_fast = 2.0 / (fast_p + 1.0)
    k_slow = 2.0 / (slow_p + 1.0)
    k_sig = 2.0 / (signal_p + 1.0)
    ema_fast = np.empty(n, dtype=np.float64)
    ema_slow = np.empty(n, dtype=np.float64)
    out_sig = np.empty(n, dtype=np.float64)

    cur_f = p[0]
    cur_s = p[0]
    cur_sig = 0.0
    for i in range(n):
        cur_f = p[i] * k_fast + cur_f * (1.0 - k_fast)
        cur_s = p[i] * k_slow + cur_s * (1.0 - k_slow)
        ema_fast[i] = cur_f
        ema_slow[i] = cur_s
        m = cur_f - cur_s
        if i == 0:
            cur_sig = m
        else:
            cur_sig = m * k_sig + cur_sig * (1.0 - k_sig)
        out_sig[i] = cur_sig

    macd_line = ema_fast - ema_slow
    return macd_line, out_sig, macd_line - out_sig


def fast_ncm_similarity(query: np.ndarray, matrix: np.ndarray) -> np.ndarray:
    """Calculate cosine similarity between query vector and matrix of concept vectors.

    Accelerated via native Rust kernel with NumPy fallback.
    """
    q = np.ascontiguousarray(query, dtype=np.float32)
    m = np.ascontiguousarray(matrix, dtype=np.float32)
    dim = len(q)
    num_concepts = len(m)
    if dim == 0 or num_concepts == 0:
        return np.empty(0, dtype=np.float32)

    if _rs is not None and hasattr(_rs, "delta_ncm_similarity"):
        out_scores = np.empty(num_concepts, dtype=np.float32)
        _rs.delta_ncm_similarity(
            q.ctypes.data, m.ctypes.data, dim, num_concepts, out_scores.ctypes.data
        )
        return out_scores

    q_norm = np.linalg.norm(q)
    if q_norm < 1e-12:
        return np.zeros(num_concepts, dtype=np.float32)
    m_norms = np.linalg.norm(m, axis=1)
    dots = np.dot(m, q)
    valid = m_norms > 1e-12
    return np.where(valid, dots / (q_norm * np.maximum(m_norms, 1e-12)), 0.0).astype(np.float32)


def fast_ncm_entropy(probs: np.ndarray) -> float:
    """Calculate Shannon entropy for a probability distribution.

    Accelerated via native Rust kernel with NumPy fallback.
    """
    p = np.ascontiguousarray(probs, dtype=np.float64)
    if len(p) == 0:
        return 0.0

    if _rs is not None and hasattr(_rs, "delta_ncm_entropy"):
        return float(_rs.delta_ncm_entropy(p.ctypes.data, len(p)))

    pos = p[p > 1e-12]
    if len(pos) == 0:
        return 0.0
    return float(-np.sum(pos * np.log(pos)))


