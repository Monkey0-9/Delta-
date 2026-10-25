"""Tests for Quantitative Certification Protocol and Multiple-Testing Adjustments.

Verifies:
1. Deflated Sharpe Ratio calculation correctly penalizes multiple trials.
2. Under-performing strategies fail R2-R6 gates and remain RESEARCH_ONLY.
3. Robust strategies with high OOS Sharpe, controlled drawdown, and capacity achieve candidate status.
"""
from __future__ import annotations

import pytest
from research.certification_protocol import QuantitativeCertifier, QuantitativeAuditManifest


def test_deflated_sharpe_ratio_penalizes_search_trials():
    # 10 trials with strong Sharpe 2.0
    dsr_few = QuantitativeCertifier.calculate_deflated_sharpe_ratio(
        est_sharpe=2.0, num_trials=10, sample_length=252
    )
    assert dsr_few > 0.0

    # 5,000 trials with Sharpe 2.5 collapses to 0.0 (selection bias)
    dsr_many = QuantitativeCertifier.calculate_deflated_sharpe_ratio(
        est_sharpe=2.5, num_trials=5000, sample_length=500, skewness=0.1, kurtosis=3.2
    )
    assert dsr_many == 0.0


def test_strategy_evaluation_fails_when_unstable():
    # Strategy with good IS Sharpe but collapsed OOS and high drawdown
    res = QuantitativeCertifier.evaluate_strategy(
        name="overfit_alpha",
        in_sample_sharpe=2.5,
        out_of_sample_sharpe=0.3,
        num_trials=5000,
        sample_bars=252,
        max_drawdown_pct=35.0,
        turnover_daily=3.0,
        universe_capacity_usd=1_000_000.0,
    )
    assert res.promotable_to_live is False
    assert res.verdict == "RESEARCH_ONLY"

    # Check individual gate failures
    gates_by_id = {g.gate_id: g for g in res.gates}
    assert gates_by_id["R3_oos"].passed is False
    assert gates_by_id["R4_stress"].passed is False
    assert gates_by_id["R5_capacity"].passed is False
    assert gates_by_id["R6_execution"].passed is False


def test_strategy_evaluation_passes_when_institutional_grade():
    res = QuantitativeCertifier.evaluate_strategy(
        name="stat_arb_v2",
        in_sample_sharpe=2.2,
        out_of_sample_sharpe=1.9,
        num_trials=10,
        sample_bars=1000,
        max_drawdown_pct=8.5,
        turnover_daily=0.4,
        universe_capacity_usd=25_000_000.0,
    )
    assert res.promotable_to_live is True
    assert res.verdict == "LIVE_CANDIDATE"
    assert all(g.passed for g in res.gates)


def test_benjamini_hochberg_fdr_control():
    # 10 factor tests: 2 true signals with small p-values, rest noise
    p_vals = [0.001, 0.004, 0.08, 0.15, 0.22, 0.45, 0.60, 0.75, 0.82, 0.95]
    sig_flags, thresh = QuantitativeCertifier.benjamini_hochberg_fdr(p_vals, target_fdr=0.05)

    assert sig_flags[0] is True  # 0.001 < 0.05 * 1/10 = 0.005
    assert sig_flags[1] is True  # 0.004 < 0.05 * 2/10 = 0.010
    assert sig_flags[2] is False # 0.08 > 0.05 * 3/10 = 0.015
    assert sum(sig_flags) == 2
    assert thresh == 0.004

