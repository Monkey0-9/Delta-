"""Stage-4 Validation tests: DeltaBench, parity, promotion gates, drift, evidence graph."""
from __future__ import annotations

import numpy as np


def test_deltabench_metrics_and_ci_gate():
    from bench.DeltaBench.suite import (brier, information_coefficient, mae,
                                        max_drawdown, regression_gate, rmse, sharpe)
    y = np.array([0.01, 0.02, -0.01, 0.03])
    p = np.array([0.011, 0.019, -0.009, 0.028])
    assert mae(y, p) < 0.01 and rmse(y, p) < 0.01
    assert information_coefficient(y, p) > 0.9
    assert brier(np.array([0, 1, 1]), np.array([0.1, 0.9, 0.8])) < 0.1
    assert sharpe(np.array([0.01] * 100)) > 5
    assert max_drawdown(np.array([100.0, 110.0, 105.0, 120.0])) < 0.05
    scores = regression_gate(y, p)
    assert all(s.passed for s in scores)


def test_sim_backtest_parity():
    from simulation.parity import assert_parity, simulate_fills
    import pytest
    px = [100.0, 101.0, 102.0]
    a = simulate_fills(px, 10.0, spread=0.01, fee_bps=1.0)
    b = simulate_fills(px, 10.0, spread=0.01, fee_bps=1.0)
    assert_parity(a, b)
    with pytest.raises(ValueError):
        assert_parity(a, a + 1.0)


def test_promotion_blocked_without_full_evidence():
    from validation.promotion import PromotionBlocked, PromotionEvidence, require_promotion
    import pytest
    good = PromotionEvidence(oos_sharpe=1.2, dsr_pvalue=0.01, pbo=0.2,
                             oos_bars=500, cost_aware=True, sharpe_backtest=2.5)
    require_promotion(good)
    bad_sharpe_only = PromotionEvidence(oos_sharpe=-0.1, dsr_pvalue=0.4, pbo=0.7,
                                        oos_bars=60, cost_aware=False,
                                        sharpe_backtest=2.8)
    with pytest.raises(PromotionBlocked):
        require_promotion(bad_sharpe_only)


def test_drift_monitor_demotes():
    import numpy as np
    from quant.monitoring.drift import check_drift, psi
    rng = np.random.default_rng(0)
    base = rng.normal(0, 1, 2000)
    same = rng.normal(0, 1, 2000)
    assert psi(base, same) < 0.2
    shifted = rng.normal(2.0, 1, 2000)
    rep = check_drift("feature", base, shifted)
    assert rep.demote and rep.psi > 0.5


def test_evidence_graph_chain():
    from provenance.evidence_graph import EvidenceGraph
    g = EvidenceGraph()
    g.add("dataset", "D1", [], {"hash": "abc"})
    g.add("feature", "F1", ["D1"], {"v": "f1"})
    g.add("model", "M1", ["F1"], {"arch": "ridge"})
    g.add("experiment", "E1", ["M1", "D1"], {"oos": 0.08})
    assert g.verify()
    lin = g.lineage("E1")
    assert {"D1", "F1", "M1", "E1"} <= set(lin)
