"""Step-1 bridge tests: live engine wired to the delta_omega kernel.

Verifies one price source per scan (with src provenance), the SVD gate,
LW+MVO allocation caps, and the uncatchable red-button halt. No mocks on
math: asserts on kernel behavior through the real call-sites.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest


def test_kernel_aliases_are_one_source():
    from delta_omega import portfolio_exec as pe
    from delta_omega import alpha_risk as ar

    assert pe.sqrt_transient_impact(100, 50.0, 0.02, 1e6, 0.01) == pytest.approx(
        pe.sqrt_impact_cost(100, 50.0, 0.02, 1e6, 0.01)
    )
    rng = np.random.default_rng(0)
    a = rng.normal(size=20)
    Q = rng.normal(size=(20, 2))
    assert np.allclose(ar.svd_orthogonalize(a, Q), ar.orthogonalize(a, Q))


def test_execution_price_formula_and_slicing():
    from delta_omega.portfolio_exec import AlmgrenChrissTrajectory, execution_price

    px_buy = execution_price(100.0, "buy", 1000.0, 0.02, 1_000_000.0, 0.02)
    px_sell = execution_price(100.0, "sell", 1000.0, 0.02, 1_000_000.0, 0.02)
    assert px_buy > 100.0 > px_sell
    # spread/2 + gamma*sigma*sqrt(q/V)*mid
    expect = 100.0 + 0.01 + 0.5 * 0.02 * np.sqrt(1000 / 1_000_000) * 100.0
    assert px_buy == pytest.approx(expect)
    assert AlmgrenChrissTrajectory.needs_slicing(150_000, 1_000_000) is True
    assert AlmgrenChrissTrajectory.needs_slicing(50_000, 1_000_000) is False
    with pytest.raises(ValueError):
        execution_price(100.0, "hold", 10.0, 0.02, 1e6, 0.01)


def test_simulation_engine_helpers_carry_provenance():
    from simulation.backtest import engine as be

    px, src = be.execution_price_with_impact(100.0, "buy", 500.0, 0.02, 1e6, 0.02)
    assert px > 100.0 and src == "delta_omega:sqrt_transient_impact"
    assert be.order_needs_slicing(200_000, 1_000_000) is True
    slices, src2 = be.slice_order_ac(1000.0, 1.0, 11, 0.3, 1e-6, 1e-7, 1e-6)
    assert src2 == "delta_omega:almgren_chriss"
    assert abs(sum(slices) - 1000.0) < 1e-6


def test_realistic_backtester_wired_to_kernel():
    from quant.backtest.realistic import (
        MarketImpactCalculator,
        MarketImpactModel,
        kernel_execution_price,
        kernel_needs_slicing,
    )
    from delta_omega.portfolio_exec import sqrt_transient_impact

    calc = MarketImpactCalculator(MarketImpactModel.SQUARE_ROOT)
    got = calc.calculate_impact("buy", 1000.0, 1_000_000.0, 0.02, 50.0)
    cost = sqrt_transient_impact(1000.0, 50.0, 0.02, 1_000_000.0 * 50.0, 0.0, gamma=0.03)
    assert got == pytest.approx((cost / (1000.0 * 50.0)) * 10000)
    assert calc.impact_source() == "delta_omega"
    px, src = kernel_execution_price(50.0, "sell", 100.0, 0.02, 1e6, 0.01)
    assert px < 50.0 and src == "delta_omega"
    assert kernel_needs_slicing(200_000, 1_000_000) is True


def test_orthogonal_gate_accepts_novel_rejects_collinear(caplog):
    import logging

    from quant.signals.orthogonal_gate import build_factor_basis, orthogonalize_alpha

    rng = np.random.default_rng(1)
    market = rng.normal(size=30)
    novel = rng.normal(size=30)
    Q = build_factor_basis(market)
    out = orthogonalize_alpha(novel, Q, alpha_name="novel_5d_rev")
    assert abs(float(np.linalg.norm(out)) - 1.0) < 1e-9

    dup = market * 3.0 + 1e-9 * rng.normal(size=30)
    with caplog.at_level(logging.WARNING, logger="quant.signals.orthogonal_gate"):
        with pytest.raises(ValueError):
            orthogonalize_alpha(dup, Q, alpha_name="clone_alpha")
    assert any("clone_alpha" in r.message and "residual variance < 0.25" in r.message for r in caplog.records)


def test_lw_mvo_bridge_respects_caps():
    from quant.portfolio.optimizer import PortfolioOptimizer, allocate_delta_omega

    rng = np.random.default_rng(5)
    X = rng.normal(size=(120, 4))
    alpha = np.array([0.10, 0.05, 0.08, 0.02])
    w, delta = allocate_delta_omega(alpha, X, lam=1.0, lmax=1.0)
    assert float(np.abs(w).sum()) <= 1.0 + 1e-9
    assert float(np.abs(w).max()) <= 0.05 + 1e-9
    assert 0.0 <= delta <= 1.0

    cols = ["A", "B", "C", "D"]
    opt = PortfolioOptimizer()
    res = opt.optimize_delta_omega(
        pd.Series(alpha, index=cols), pd.DataFrame(X, columns=cols)
    )
    assert res.optimization_status == "success" and res.constraints_satisfied
    assert abs(float(res.weights.sum())) <= 1.0 + 1e-9
    assert res.metadata["src"] == "delta_omega"


def test_red_button_halts_before_approval():
    from delta_omega.agent_ledger_gate import GateState, RiskHaltException, TOOL_REGISTRY
    from risk.firewall.firewall import RiskFirewall, enforce_red_button

    clean = GateState(99, 100, 0.01, 0.05, 0.05, 0.995, False, 0.02, 0.01, 0.05, True, True, True)
    enforce_red_button(clean)  # no raise
    bad = GateState(100, 99, 0.2, 0.05, 0.5, 0.5, True, 0.5, 0.5, 0.05, False, False, False)
    with pytest.raises(RiskHaltException):
        enforce_red_button(bad)

    import importlib.util as _ilu

    import sys as _sys

    _spec = _ilu.spec_from_file_location("legacy_simple_firewall", "risk/firewall_legacy_float.py")
    assert _spec is not None and _spec.loader is not None
    legacy = _ilu.module_from_spec(_spec)
    _sys.modules["legacy_simple_firewall"] = legacy
    _spec.loader.exec_module(legacy)

    fw = legacy.RiskFirewall(max_quantity=100.0, max_gross=1000.0)
    with pytest.raises(RiskHaltException):
        fw.evaluate_with_red_button(
            decision_id="d1", requested_quantity=10.0,
            current_gross=0.0, limits_version="v1", gate_state=bad,
        )
    ok = fw.evaluate_with_red_button(
        decision_id="d1", requested_quantity=10.0,
        current_gross=0.0, limits_version="v1", gate_state=clean,
    )
    assert float(ok.approved_quantity) == 10.0

    assert set(("query_market_state", "calculate_factor_risk", "run_hrp_allocation", "check_red_button")) <= set(TOOL_REGISTRY)
