from decimal import Decimal
from datetime import datetime, timezone

from finance_model import (
    FinanceModel,
    FinancialAnalysisInput,
    FinancialEvidence,
)

from learning.failure_attribution.attributor import (
    FailureAttributor,
)

from learning.validation.protected_failures import (
    CandidateResult,
    FailureCase,
    ProtectedFailureRegression,
)

from memory.failures.failure import FailureType

from provenance.audit.chain import AuditChain

from provenance.evidence.evidence import Evidence

from simulation.scenarios.generator import (
    ScenarioGenerator,
)

from validation.stress.evaluator import (
    StressEvaluator,
)


def test_w9_equity_stress_is_deterministic() -> None:
    scenario = ScenarioGenerator.equity_crash(
        "CRASH-001",
        Decimal("0.25"),
    )

    result = StressEvaluator().evaluate(
        scenario,
        portfolio_value=Decimal("100000"),
        gross_exposure=Decimal("80000"),
        net_exposure=Decimal("50000"),
        leverage=Decimal("0.8"),
        positions={
            "NVDA": Decimal("30000"),
            "AAPL": Decimal("20000"),
        },
    )

    assert result.scenario_id == "CRASH-001"
    assert result.portfolio_pnl == Decimal("-25000")
    assert result.portfolio_return == Decimal("-0.25")
    assert result.breached


def test_w10_evidence_hash_is_stable() -> None:
    evidence = Evidence(
        source="market-data",
        observation="test observation",
        timestamp=datetime(
            2026,
            1,
            1,
            tzinfo=timezone.utc,
        ),
    )

    assert len(evidence.content_hash()) == 64
    assert evidence.content_hash() == evidence.content_hash()


def test_w10_audit_chain_integrity() -> None:
    chain = AuditChain()

    chain.append(
        record_type="decision",
        record_id="DEC-1",
        payload_hash="abc",
    )

    chain.append(
        record_type="order",
        record_id="ORD-1",
        payload_hash="def",
    )

    assert chain.verify()


def test_w11_failure_attribution() -> None:
    attributor = FailureAttributor()

    result = attributor.classify(
        expected_return=Decimal("0.10"),
        actual_return=Decimal("-0.02"),
        data_valid=True,
        execution_slippage=Decimal("0"),
        predicted_regime="RISK_ON",
        realized_regime="RISK_ON",
        risk_breached=False,
    )

    assert result == FailureType.MODEL_ERROR


def test_w11_protected_failure_regression() -> None:
    regression = ProtectedFailureRegression()

    cases = (
        FailureCase(
            case_id="F1",
            regime="HIGH_VOL",
            volatility=Decimal("0.60"),
            liquidity=Decimal("0.20"),
            expected_max_loss=Decimal("0.10"),
        ),
    )

    results = (
        CandidateResult(
            case_id="F1",
            actual_loss=Decimal("0.08"),
        ),
    )

    report = regression.evaluate(
        cases,
        results,
    )

    assert report.passed


def test_w12_finance_model() -> None:
    model = FinanceModel("finance-model-test-1")

    request = FinancialAnalysisInput(
        instrument="NVDA",
        world_state_version="WS-1",
        quant_state_version="QS-1",
        portfolio_context="balanced portfolio",
        horizon="medium_term",
        expected_return=Decimal("0.05"),
        uncertainty=Decimal("0.20"),
        evidence=(
            FinancialEvidence(
                source="quant",
                observation="positive expected return",
                reliability=Decimal("0.90"),
            ),
        ),
    )

    result = model.analyze(request)

    assert result.instrument == "NVDA"
    assert result.candidate_action == "BUY_CANDIDATE"
    assert result.confidence == Decimal("0.80")
    assert result.model_version == "finance-model-test-1"