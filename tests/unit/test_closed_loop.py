"""P4: closed learning loop - record, recall, promote."""
from __future__ import annotations

from decimal import Decimal

from learning.closed_loop import ClosedLoopLedger, evaluate_promotion
from memory.failures.failure import FailureType


def test_record_routes_each_failure_branch():
    led = ClosedLoopLedger()
    rec, exp = led.record_trade_outcome(
        decision_id="d1", instrument="AAPL", horizon="today", regime="calm",
        expected_return=Decimal("0.05"), actual_return=Decimal("-0.05"),
        data_valid=False,
    )
    assert rec.failure_type == FailureType.DATA_ERROR
    assert exp.failure_type == FailureType.DATA_ERROR.value

    led2 = ClosedLoopLedger()
    rec2, _ = led2.record_trade_outcome(
        decision_id="d2", instrument="AAPL", horizon="today", regime="calm",
        expected_return=Decimal("0.01"), actual_return=Decimal("0.011"),
        predicted_regime="calm", realized_regime="calm",
    )
    assert rec2.failure_type == FailureType.NO_FAILURE


def test_recall_prefers_exact_match_as_evidence():
    led = ClosedLoopLedger()
    led.record_trade_outcome(
        decision_id="d1", instrument="AAPL", horizon="today", regime="volatile",
        expected_return=Decimal("0.05"), actual_return=Decimal("-0.05"),
    )
    led.record_trade_outcome(
        decision_id="d2", instrument="MSFT", horizon="week", regime="calm",
        expected_return=Decimal("0.05"), actual_return=Decimal("-0.05"),
    )
    got = led.recall(instrument="AAPL", regime="volatile", horizon="today")
    assert got and got[0].instrument == "AAPL"
    assert led.recall(instrument="ZZZ", regime="zzz", horizon="zzz") == ()


def test_promotion_gate_rejects_incomplete_evidence():
    d = evaluate_promotion(
        walk_forward_passed=True, out_of_sample_passed=False,
        stress_passed=True, regression_passed=True, protected_failures_passed=True,
    )
    assert d.status.value in ("rejected", "REJECTED")
    ok = evaluate_promotion(
        walk_forward_passed=True, out_of_sample_passed=True,
        stress_passed=True, regression_passed=True, protected_failures_passed=True,
    )
    assert ok.status.value in ("candidate", "CANDIDATE")
