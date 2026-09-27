from finance_model.evaluation.release_gate import (
    ModelReleaseGate,
    ReleaseGateInput,
)


def test_release_gate_passes_only_when_all_pass():

    gate = ReleaseGateInput(
        schema_valid=True,
        grounding_passed=True,
        calibration_passed=True,
        abstention_passed=True,
        tool_selection_passed=True,
        tool_correctness_passed=True,
        protected_failures_passed=True,
        oos_validation_passed=True,
        stress_validation_passed=True,
        regression_passed=True,
    )

    result = ModelReleaseGate().evaluate(gate)

    assert result.passed
    assert result.failed_gates == ()


def test_release_gate_fails_closed():

    gate = ReleaseGateInput(
        schema_valid=True,
        grounding_passed=True,
        calibration_passed=False,
        abstention_passed=True,
        tool_selection_passed=True,
        tool_correctness_passed=True,
        protected_failures_passed=True,
        oos_validation_passed=True,
        stress_validation_passed=True,
        regression_passed=True,
    )

    result = ModelReleaseGate().evaluate(gate)

    assert not result.passed
    assert "calibration" in result.failed_gates