"""Institutional gates: canonical unification, protected seeds, shadow promotion."""
from decimal import Decimal

from core.contracts.canonical import FailureCategory, normalize_failure_category
from deployment.shadow import ShadowDecision, ShadowRunner
from learning.validation.protected_failures import (
    CandidateResult,
    ProtectedFailureRegression,
    seeded_protected_cases,
)
from observability.audit_chain import AuditChain as ObsChain
from observability.chaos import ChaosRunner, FailureMode
from provenance.audit.chain import AuditChain as ProvChain


def test_failure_vocab_unified():
    assert normalize_failure_category("PREDICTION") is FailureCategory.MODEL_ERROR
    assert normalize_failure_category("news") is FailureCategory.EVENT_ERROR
    assert normalize_failure_category("liquidity_error") is FailureCategory.LIQUIDITY_ERROR
    from learning.failures.attribution import FailureType as Legacy

    assert Legacy.PREDICTION.to_canonical() is FailureCategory.MODEL_ERROR


def test_protected_seeds_regress():
    cases = seeded_protected_cases()
    assert len(cases) >= 15
    reg = ProtectedFailureRegression()
    ok = tuple(CandidateResult(c.case_id, c.expected_max_loss) for c in cases)
    assert reg.evaluate(cases, ok).passed is True
    bad = tuple(
        CandidateResult(c.case_id, c.expected_max_loss + Decimal("5")) for c in cases[:1]
    ) + tuple(CandidateResult(c.case_id, c.expected_max_loss) for c in cases[1:])
    rep = reg.evaluate(cases, bad)
    assert rep.passed is False and rep.failed_cases == (cases[0].case_id,)


def test_shadow_promotion_thresholds():
    r = ShadowRunner()
    for i in range(35):
        r.record(ShadowDecision("cand-a", "BUY", 10.0, "BUY", 5.0))
    d = r.promotion_decision("cand-a", min_observations=30, min_mean_pnl=0.0)
    assert d["decision"] == "PROMOTE"
    assert r.promotion_decision("unknown")["decision"] == "HOLD"


def test_chaos_fail_closed_and_audit_unified():
    res = ChaosRunner().run(FailureMode.DATA_FEED_LOSS, lambda m: True)
    assert res.recovered is True and res.fail_closed is True
    assert issubclass(ObsChain, ProvChain)
    c = ObsChain()
    h = c.append({"type": "test.event", "id": "e1"})
    assert c.verify() is True and c.head == h == c.head_hash
