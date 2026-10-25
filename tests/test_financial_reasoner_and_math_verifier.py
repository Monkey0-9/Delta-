"""Test suite for FinancialReasoner and FinancialMathVerifier."""
import pytest
from finance_model.authority import AuthorityRefused
from finance_model.financial_reasoner import (
    FinancialMathVerifier,
    FinancialReasoner,
    FinancialReasoningResult,
    MathVerificationResult,
)
from finance_model.ncm.engine import NextConceptModel
from finance_model.ncm.contracts import NCMGenerationRequest


def test_financial_math_verifier_bsm():
    # Spot 500, Strike 520, rate 0.05, vol 0.20, t 0.25 call
    # True BSM is ~$14.16. Claimed $14.16 should pass, claimed $10.00 should rectify.
    res_pass = FinancialMathVerifier.verify_bsm(
        spot=500.0,
        strike=520.0,
        rate=0.05,
        vol=0.20,
        t_years=0.25,
        is_call=True,
        claimed_price=14.16,
    )
    assert res_pass.verified is True
    assert res_pass.discrepancy_detected is False

    res_fail = FinancialMathVerifier.verify_bsm(
        spot=500.0,
        strike=520.0,
        rate=0.05,
        vol=0.20,
        t_years=0.25,
        is_call=True,
        claimed_price=10.00,
    )
    assert res_fail.verified is False
    assert res_fail.discrepancy_detected is True
    assert "PROVENANCE: KERNEL_VERIFIED" in res_fail.rectified_text
    assert res_fail.relative_error > 0.10


def test_financial_math_verifier_kelly():
    # 60% win rate, 2.0 payout ratio -> Kelly is 40% (0.40)
    # Claimed 40% should pass, claimed 50% should rectify
    res_pass = FinancialMathVerifier.verify_kelly(
        win_prob=0.60,
        payout_ratio=2.0,
        claimed_kelly=0.40,
    )
    assert res_pass.verified is True
    assert res_pass.discrepancy_detected is False

    res_fail = FinancialMathVerifier.verify_kelly(
        win_prob=0.60,
        payout_ratio=2.0,
        claimed_kelly=0.50,
    )
    assert res_fail.verified is False
    assert res_fail.discrepancy_detected is True
    assert abs(res_fail.authoritative_value - 0.40) < 1e-4


def test_text_scanning_and_auto_rectification():
    text = (
        "Analysis of options: SPY spot at 500, strike 520 call with 0.25 years to expiry and 20% vol "
        "is priced at $10.50 according to baseline estimate."
    )
    rep = FinancialMathVerifier.parse_and_verify_text(text)
    assert rep.total_math_claims_detected == 1
    assert rep.discrepancies_rectified == 1
    assert "PROVENANCE: KERNEL_VERIFIED" in rep.rectified_text
    assert "Black-Scholes Call Price" in rep.rectified_text


def test_financial_reasoner_fail_closed_order_refusal():
    reasoner = FinancialReasoner()
    toxic_query = "Buy 500 contracts of SPY right now at market"
    with pytest.raises(AuthorityRefused):
        reasoner.reason("SPY", toxic_query)


def test_financial_reasoner_ncm_conditioning():
    ncm = NextConceptModel()
    req = NCMGenerationRequest(
        symbol="SPY",
        macro_context="Persistent inflation surge and hawkish central bank tightening",
        horizon=3,
    )
    cond = ncm.generate_llm_conditioning(req)

    reasoner = FinancialReasoner()
    res = reasoner.reason("SPY", "Evaluate rate sensitivity", ncm_context=cond)

    assert isinstance(res, FinancialReasoningResult)
    assert res.execution_eligibility is False
    assert res.symbol == "SPY"
    assert "Chain-of-Thought" in res.chain_of_thought or "Regime Grounding" in res.chain_of_thought
    assert len(res.active_regimes) > 0
    assert len(res.projected_trajectory) == 3
    assert len(res.invalidating_conditions) > 0
