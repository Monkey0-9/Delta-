from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class EvaluationMetrics:
    task_accuracy: float
    calibration_error: float
    abstention_quality: float
    temporal_integrity: float
    protected_failure_pass_rate: float


@dataclass(frozen=True, slots=True)
class ReleaseThresholds:
    min_accuracy: float = 0.60
    max_calibration_error: float = 0.10
    min_abstention_quality: float = 0.70
    min_temporal_integrity: float = 1.0
    min_protected_failure_pass_rate: float = 1.0


@dataclass(frozen=True, slots=True)
class RegressionResult:
    passed: bool
    failures: tuple[str, ...]


def evaluate_release(
    metrics: EvaluationMetrics,
    thresholds: ReleaseThresholds,
) -> RegressionResult:
    failures: list[str] = []

    if metrics.task_accuracy < thresholds.min_accuracy:
        failures.append("accuracy_below_threshold")

    if metrics.calibration_error > thresholds.max_calibration_error:
        failures.append("calibration_error_above_threshold")

    if metrics.abstention_quality < thresholds.min_abstention_quality:
        failures.append("abstention_quality_below_threshold")

    if metrics.temporal_integrity < thresholds.min_temporal_integrity:
        failures.append("temporal_integrity_failed")

    if (
        metrics.protected_failure_pass_rate
        < thresholds.min_protected_failure_pass_rate
    ):
        failures.append("protected_failure_regression_failed")

    return RegressionResult(
        passed=not failures,
        failures=tuple(failures),
    )