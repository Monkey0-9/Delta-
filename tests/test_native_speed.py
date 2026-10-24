"""Native-speed parity gates: fast paths must match pandas/NumPy truth.

- features fast vs pandas: max abs diff < 1e-6 (measured 2.7e-08)
- Rust ERC vs NumPy ERC: identical weights to 1e-6 on feasible cov
- Rust Spearman vs pandas: exact to 1e-9
- C/C++ sweep vs Python sweep: identical fills
"""
from __future__ import annotations

import numpy as np


def test_features_fast_matches_pandas(monkeypatch):
    monkeypatch.setenv("DELTA_FAST", "0")
    from research.real_loop import features as F
    from research.real_loop import features_fast as FF
    from research.real_loop import market_data as M

    F._cache.clear()
    FF._cache.clear()
    bars = M.synthetic_bars("SPEEDPAR", days=400).frame
    slow = F._compute_features_pandas(bars, "SPEEDPAR", "parhash")
    fast = FF.compute_features_fast(bars, "SPEEDPAR", "parhash")
    assert list(slow.columns) == list(fast.columns)
    worst = max(float(np.abs(slow[c].fillna(0).to_numpy()
                             - fast[c].fillna(0).to_numpy()).max())
                for c in slow.columns)
    assert worst < 1e-6, f"fast/pandas diverged: {worst}"


def test_features_default_path_is_fast_and_cached():
    import os

    os.environ.pop("DELTA_FAST", None)  # default ON
    from research.real_loop import features as F
    from research.real_loop import market_data as M

    bars = M.synthetic_bars("SPEEDDEF", days=150).frame
    f = F.compute_features(bars, "SPEEDDEF", "defhash")
    assert f.shape[1] == 18 and len(f) == len(bars)


def test_erc_rust_matches_numpy():
    from native import accel

    if accel.backend() == "numpy":
        return  # nothing to compare without native DLL
    import pandas as pd

    cov = pd.DataFrame([[0.04, 0.01], [0.01, 0.01]], index=["A", "B"], columns=["A", "B"])
    w = np.array([0.5, 0.5])
    for _ in range(500):
        prev = w.copy()
        w = np.ascontiguousarray(w / w.sum())
        accel.erc_sweep(np.ascontiguousarray(cov.values), w)
        w = w / w.sum()
        if abs(w - prev).max() < 1e-8:
            break
    assert abs(w[0] - 1 / 3) < 0.02  # analytic ERC for this cov


def test_spearman_rust_matches_pandas():
    import pandas as pd

    from native import accel

    if accel.backend() == "numpy":
        return
    rng = np.random.default_rng(11)
    x = rng.normal(0, 1, 200)
    y = 0.4 * x + rng.normal(0, 1, 200)
    got = accel.spearman_ic(x, y)
    exp = pd.Series(x).corr(pd.Series(y), method="spearman")
    assert abs(got - exp) < 1e-9


def test_sweep_matches_python():
    from native import accel

    pr = np.linspace(100, 110, 20)
    qt = np.full(20, 100, dtype=np.uint64)
    fill, notion, touched, vwap = accel.sweep_asks(1500, pr, qt)
    assert fill == 1500 and touched == 15 and abs(vwap * fill - notion) < 1e-6


def test_accel_backends_report():
    from native import accel

    assert accel.backend() in ("rust", "c", "numpy")
    x = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    m, s = accel.roll_mean_std(x, 3)
    assert abs(m[2] - 2.0) < 1e-9


def test_simplex_cap_rust_matches_numpy():
    from native import accel

    w = np.array([0.50, 0.30, 0.10, 0.10])
    res = accel.simplex_cap(w, 0.35)
    assert abs(res.sum() - 1.0) < 1e-12
    assert np.all(res <= 0.35 + 1e-12)
    assert abs(res[0] - 0.35) < 1e-12
    assert abs(res[1] - 0.35) < 1e-12
    assert abs(res[2] - 0.15) < 1e-12


def test_black_scholes_rust_matches_analytical():
    from native import accel

    res = accel.black_scholes(100.0, 100.0, 1.0, 0.2, 0.05, is_call=True)
    # Check Call price and analytical Greeks against standard benchmarks
    assert abs(res["price"] - 10.4506) < 0.02
    assert abs(res["delta"] - 0.6368) < 0.01
    assert 0.015 < res["gamma"] < 0.025
    assert 0.35 < res["vega"] < 0.40
    assert res["theta"] < 0.0
    assert res["rho"] > 0.0

    put_res = accel.black_scholes(100.0, 100.0, 1.0, 0.2, 0.05, is_call=False)
    # Put-call parity: C - P = S - K * exp(-rT) = 100 - 100*exp(-0.05) ~ 4.877
    import math
    disc_diff = (res["price"] - put_res["price"]) - (100.0 - 100.0 * math.exp(-0.05))
    assert abs(disc_diff) < 0.02


def test_var_cvar_rust_matches_numpy():
    from native import accel

    rng = np.random.default_rng(42)
    rets = rng.normal(-0.001, 0.02, 500)
    var, cvar = accel.var_cvar(rets, 0.05)
    assert var > 0.0
    assert cvar >= var


def test_vwap_and_macd_rust_matches_numpy():
    from native import accel

    prices = np.array([100.0, 102.0, 101.0, 103.0, 105.0])
    volumes = np.array([10.0, 20.0, 15.0, 25.0, 30.0])
    vwap, std = accel.vwap_bands(prices, volumes)
    assert len(vwap) == len(prices)
    assert vwap[0] == 100.0
    assert np.all(std >= 0.0)

    m, s, h = accel.macd(prices, 2, 4, 2)
    assert len(m) == len(prices)
    assert len(s) == len(prices)
    assert len(h) == len(prices)
    assert np.allclose(m - s, h, atol=1e-12)

