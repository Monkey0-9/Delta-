from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ReleaseGateInput:
    schema_valid: bool
    grounding_passed: bool
    calibration_passed: bool
    abstention_passed: bool

    tool_selection_passed: bool
    tool_correctness_passed: bool

    protected_failures_passed: bool

    oos_validation_passed: bool
    stress_validation_passed: bool

    regression_passed: bool


@dataclass(frozen=True, slots=True)
class ReleaseGateResult:
    passed: bool
    failed_gates: tuple[str, ...]


class ModelReleaseGate:

    def evaluate(
        self,
        gate: ReleaseGateInput,
    ) -> ReleaseGateResult:

        checks = {
            "schema": gate.schema_valid,
            "grounding": gate.grounding_passed,
            "calibration": gate.calibration_passed,
            "abstention": gate.abstention_passed,
            "tool_selection": gate.tool_selection_passed,
            "tool_correctness": gate.tool_correctness_passed,
            "protected_failures": gate.protected_failures_passed,
            "oos_validation": gate.oos_validation_passed,
            "stress_validation": gate.stress_validation_passed,
            "regression": gate.regression_passed,
        }

        failed = tuple(
            name
            for name, passed in checks.items()
            if not passed
        )

        return ReleaseGateResult(
            passed=len(failed) == 0,
            failed_gates=failed,
        )