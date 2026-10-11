"""P2/I: one sanctioned cost formula; engine-produced cost-adjusted Sharpe."""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

sys.path.insert(0, ".")

from execution.cost_engine import TransactionCostEngine
from research.real_loop.backtest import CostModel, _dynamic_costs


def _frame(n: int = 100, seed: int = 3):
    idx = pd.date_range("2024-01-01", periods=n, freq="D", tz="UTC")
    rng = np.random.default_rng(seed)
    close = pd.Series(100 * np.cumprod(1 + rng.normal(0, 0.01, n)), index=idx)
    frame = pd.DataFrame({"close": close, "volume": 1e6}, index=idx)
    churn = pd.Series(np.abs(rng.normal(0, 0.5, n)), index=idx)
    return frame, churn


def test_engine_backtest_parity_bit_identical():
    """The backtest delegates to the engine: identical numbers to the
    documented v3 formula (float noise only)."""
    frame, churn = _frame()
    dec, avg = _dynamic_costs(frame, churn, CostModel())
    part = 0.02 * (1 + churn.fillna(0))
    impact = 8.0 * np.sqrt(part.clip(lower=0))
    vol = frame["close"].pct_change().rolling(20).std().fillna(0.015)
    spread = 5.0 * (1 + 0.5 * (vol / 0.015 - 1).clip(lower=0))
    per = spread / 2 + 1.0 + 2.0 + impact
    assert float((dec - churn * per / 1e4).abs().max()) < 1e-12
    assert abs(avg - float(per.mean())) < 1e-12


def test_quotes_stamp_proxy_lineage():
    e = TransactionCostEngine()
    q = e.quote(qty=50_000, adv=10_000_000, sigma=0.02, spread_bps=2.0)
    assert q.proxy is True and e.is_proxy is True
    assert q.total_bps > 0
    cal = TransactionCostEngine(calibrated=True, calibration_id="fills-2026-10")
    q2 = cal.quote(qty=50_000, adv=10_000_000, sigma=0.02, spread_bps=2.0)
    assert q2.proxy is False and cal.is_proxy is False
    assert q2.total_bps == q.total_bps  # lineage flag only


def test_cost_adjusted_sharpe_produced_by_engine():
    """research_statistics emits an engine-computed, proxy-labeled
    cost_adjusted_sharpe — the promotion gate's required evidence."""
    from research.real_loop import features as F
    from research.real_loop.validate import research_statistics

    idx = pd.date_range("2024-01-01", periods=300, freq="D", tz="UTC")
    rng = np.random.default_rng(11)
    close = pd.Series(100 * np.cumprod(1 + rng.normal(0.001, 0.01, 300)),
                       index=idx)
    frame = pd.DataFrame(
        {"open": close, "high": close * 1.005, "low": close * 0.995,
         "close": close, "volume": 2_000_000}, index=idx)
    feat = F.compute_features(frame, "COST", "hash-cost")
    st = research_statistics(frame, feat)
    assert "cost_adjusted_sharpe" in st and "cost_proxy" in st, st.keys()
    assert st["cost_proxy"] is True  # engine uncalibrated: labeled, not hidden
    assert isinstance(st["cost_adjusted_sharpe"], float)
