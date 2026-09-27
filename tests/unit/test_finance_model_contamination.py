import pytest

from finance_model.datasets.contamination import (
    ContaminationDetector,
)
from finance_model.datasets.schema import (
    DatasetStage,
    Evidence,
    FinanceExample,
)


def test_future_evidence_is_rejected():

    example = FinanceExample(
        example_id="x",
        stage=DatasetStage.SFT,
        prompt="test",
        response="test",
        decision_time="2025-01-01T00:00:00+00:00",
        evidence=(
            Evidence(
                evidence_id="future",
                source="test",
                published_at="2025-01-02T00:00:00+00:00",
                effective_at="2025-01-02T00:00:00+00:00",
                text="future information",
            ),
        ),
    )

    with pytest.raises(ValueError):
        example.validate_temporal_integrity()


def test_clean_example_passes():

    example = FinanceExample(
        example_id="clean",
        stage=DatasetStage.SFT,
        prompt="test",
        response="test",
        decision_time="2025-01-02T00:00:00+00:00",
        evidence=(
            Evidence(
                evidence_id="past",
                source="test",
                published_at="2025-01-01T00:00:00+00:00",
                effective_at="2025-01-01T00:00:00+00:00",
                text="historical information",
            ),
        ),
    )

    example.validate_temporal_integrity()

    report = ContaminationDetector().inspect(
        [example]
    )

    assert report.passed