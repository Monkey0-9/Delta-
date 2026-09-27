from __future__ import annotations

import math

import pytest

from finance_model.datasets.drift import (
    DistributionDriftDetector,
)
from finance_model.datasets.quality_gate import (
    DatasetQualityGate,
)


def _row(
    record_id: str,
    price: float,
    volume: float,
) -> dict[str, object]:
    return {
        "record_id": record_id,
        "asset": "NVDA",
        "decision_time": "2026-01-01T10:00:00+00:00",
        "close": price,
        "volume": volume,
    }


def test_quality_gate_accepts_valid_data() -> None:
    gate = DatasetQualityGate(
        numeric_fields=(
            "close",
            "volume",
        ),
        min_numeric={
            "close": 0.0,
            "volume": 0.0,
        },
    )

    report = gate.validate(
        [
            _row("a", 100.0, 1000.0),
            _row("b", 101.0, 1100.0),
        ]
    )

    assert report.passed is True
    assert report.violation_count == 0


def test_quality_gate_detects_missing_required_field() -> None:
    gate = DatasetQualityGate()

    report = gate.validate(
        [
            {
                "record_id": "a",
                "decision_time": (
                    "2026-01-01T10:00:00+00:00"
                ),
            }
        ]
    )

    assert report.passed is False
    assert any(
        violation.violation_type == "missing"
        for violation in report.violations
    )


def test_quality_gate_detects_nan() -> None:
    gate = DatasetQualityGate(
        numeric_fields=("close",),
    )

    report = gate.validate(
        [
            {
                "record_id": "a",
                "asset": "NVDA",
                "decision_time": (
                    "2026-01-01T10:00:00+00:00"
                ),
                "close": math.nan,
            }
        ]
    )

    assert report.passed is False


def test_quality_gate_detects_range_violation() -> None:
    gate = DatasetQualityGate(
        numeric_fields=("close",),
        min_numeric={"close": 0.0},
    )

    report = gate.validate(
        [
            _row("a", -1.0, 1000.0),
        ]
    )

    assert report.passed is False
    assert any(
        violation.violation_type == "range"
        for violation in report.violations
    )


def test_drift_detector_detects_shift() -> None:
    detector = DistributionDriftDetector(
        psi_threshold=0.05,
        mean_shift_threshold=0.10,
        std_shift_threshold=0.20,
    )

    reference = [
        {"x": float(value)}
        for value in range(100)
    ]

    current = [
        {"x": float(value + 100)}
        for value in range(100)
    ]

    report = detector.compare(
        reference,
        current,
        fields=("x",),
    )

    assert report.drifted_fields == ("x",)
    assert report.passed is False


def test_drift_detector_handles_stable_distribution() -> None:
    detector = DistributionDriftDetector()

    reference = [
        {"x": float(value)}
        for value in range(100)
    ]

    current = [
        {"x": float(value)}
        for value in range(100)
    ]

    report = detector.compare(
        reference,
        current,
        fields=("x",),
    )

    assert report.drifted_fields == ()
    assert report.passed is True


def test_drift_detector_insufficient_data() -> None:
    detector = DistributionDriftDetector()

    report = detector.compare(
        [{"x": 1.0}],
        [{"x": 2.0}],
        fields=("x",),
    )

    assert report.metrics[0].status == (
        "INSUFFICIENT_DATA"
    )