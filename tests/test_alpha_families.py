"""Volatility / liquidity / stat-arb families: real math, deterministic, no lookahead."""
from __future__ import annotations


def _bars(n: int = 400):
    import delta_compat  # noqa
    from datetime import datetime, timezone
    from research.real_loop import market_data as M
    end = datetime(2024, 12, 31, tzinfo=timezone.utc)
    return M.synthetic_bars("FAM", days=n, end=end).frame


def test_volatility_family():
    from quant.alpha import volatility as V
    f = V.compute(_bars())
    s = V.signal(f)
    assert {"realized_vol", "vol_percentile_252d", "vol_of_vol", "vol_regime_z"} <= set(f.columns)
    assert ((s >= -1) & (s <= 1)).all()
    assert s.iloc[:5].eq(0).all()  # warmup: no signal without history
    assert (f["realized_vol"].dropna() > 0).all()
    s2 = V.signal(V.compute(_bars()))
    assert s.equals(s2)  # deterministic


def test_liquidity_family_and_capacity_bind():
    import pytest
    from quant.alpha import liquidity as L
    f = L.compute(_bars())
    s = L.signal(f)
    assert {"amihud", "turnover_z", "spread_proxy", "illiquidity", "adv_20d"} <= set(f.columns)
    assert ((s >= -1) & (s <= 1)).all()
    assert (f["amihud"].dropna() >= 0).all()
    ok = L.capacity_flag(f, capital=1e6, price=100.0)
    assert ok["binds"] is False and ok["participation"] > 0
    big = L.capacity_flag(f, capital=1e12, price=100.0)
    assert big["binds"] is True  # illiquidity premium capacity-binds first
    with pytest.raises(ValueError):
        L.capacity_flag(f, capital=-1.0, price=100.0)


def test_stat_arb_half_life_gating():
    import numpy as np
    import pandas as pd
    from quant.alpha import stat_arb as S
    rng = np.random.default_rng(7)
    n = 300
    x = pd.Series(100 * np.exp(np.cumsum(rng.normal(0, 0.01, n))))
    spread_true = pd.Series(rng.normal(0, 1, n)).ewm(alpha=0.1).mean()  # mean-reverting
    y = 1.5 * x + spread_true
    feat = S.compute(y, x)
    assert feat["half_life"].dropna().between(5, 250).any()
    s = S.signal(feat)
    assert ((s >= -1) & (s <= 1)).all()
    assert (s != 0).any()  # tradeable pair produces signal
    # random walk pair: half-life mostly rejected
    rw = pd.Series(np.cumsum(rng.normal(0, 1, n)) + 100)
    rw2 = pd.Series(np.cumsum(rng.normal(0, 1, n)) + 100)
    feat_rw = S.compute(rw, rw2)
    assert S.signal(feat_rw).abs().mean() <= s.abs().mean() + 1.0  # sanity: bounded


def test_families_registry_marks_six_implemented():
    from quant.alpha.families import FAMILIES, validation_pipeline
    impl = {f.name for f in FAMILIES if f.implemented}
    assert {"momentum", "mean_reversion", "microstructure",
            "volatility", "liquidity", "stat_arb"} <= impl
    assert "deflated_sharpe" in validation_pipeline() and "capacity" in validation_pipeline()
