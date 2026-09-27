from datetime import datetime, timezone

import pytest

from finance_model.datasets.lineage import DataLineage
from finance_model.datasets.quality import (
    DatasetRecord,
    validate_records,
)
from finance_model.datasets.splitter import chronological_split
from finance_model.evaluation.abstention import (
    ConfidenceAssessment,
    DecisionDisposition,
)
from finance_model.evaluation.regression import (
    EvaluationMetrics,
    ReleaseThresholds,
    evaluate_release,
)


def test_lineage_rejects_future_availability() -> None:
    now = datetime.now(timezone.utc)

    with pytest.raises(ValueError):
        DataLineage(
            source_id="x",
            source_type="market",
            event_time=now,
            available_time=now.replace(
                year=now.year - 1
            ),
            source_version="1",
            content_hash="abc",
        )


def test_temporal_split_is_non_random() -> None:
    timestamps = [
        datetime(2020, 1, i, tzinfo=timezone.utc)
        for i in range(1, 11)
    ]

    split = chronological_split(
        timestamps,
        train_fraction=0.6,
        validation_fraction=0.2,
    )

    assert split.train == (0, 1, 2, 3, 4, 5)
    assert split.validation == (6, 7)
    assert split.test == (8, 9)


def test_dataset_duplicate_detection() -> None:
    records = [
        DatasetRecord("a", None, None),
        DatasetRecord("a", None, None),
    ]

    report = validate_records(records)

    assert report.duplicates == 1
    assert not report.valid


def test_low_confidence_abstains() -> None:
    result = ConfidenceAssessment(
        confidence=0.30,
        minimum_confidence=0.70,
        evidence_quality=0.95,
        model_agreement=0.95,
    )

    assert result.disposition == DecisionDisposition.ABSTAIN


def test_bad_calibration_blocks_release() -> None:
    result = evaluate_release(
        EvaluationMetrics(
            task_accuracy=0.90,
            calibration_error=0.20,
            abstention_quality=0.90,
            temporal_integrity=1.0,
            protected_failure_pass_rate=1.0,
        ),
        ReleaseThresholds(),
    )

    assert not result.passed
    assert "calibration_error_above_threshold" in result.failures


def test_protected_failure_is_hard_gate() -> None:
    result = evaluate_release(
        EvaluationMetrics(
            task_accuracy=0.90,
            calibration_error=0.05,
            abstention_quality=0.90,
            temporal_integrity=1.0,
            protected_failure_pass_rate=0.95,
        ),
        ReleaseThresholds(),
    )

    assert not result.passed
    assert "protected_failure_regression_failed" in result.failures