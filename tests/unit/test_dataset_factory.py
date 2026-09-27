from __future__ import annotations

import json

import pytest

from finance_model.datasets.factory import DatasetFactory
from research.data.audit import audit_dataset


def _record(
    record_id: str,
    decision_time: str,
    *,
    effective_at: str | None = None,
) -> dict[str, object]:
    return {
        "record_id": record_id,
        "asset": "NVDA",
        "decision_time": decision_time,
        "effective_at": effective_at or decision_time,
        "feature": 1.25,
    }


def test_factory_is_deterministic() -> None:
    records = [
        _record(
            "b",
            "2026-01-02T10:00:00+00:00",
        ),
        _record(
            "a",
            "2026-01-01T10:00:00+00:00",
        ),
    ]

    factory = DatasetFactory()

    first = factory.build(
        records,
        dataset_id="delta-test",
        version="1",
        source="unit-test",
    )

    second = factory.build(
        list(reversed(records)),
        dataset_id="delta-test",
        version="1",
        source="unit-test",
    )

    assert first.dataset_hash == second.dataset_hash
    assert first.records == second.records


def test_factory_rejects_duplicate_ids() -> None:
    factory = DatasetFactory()

    records = [
        _record(
            "same",
            "2026-01-01T00:00:00+00:00",
        ),
        _record(
            "same",
            "2026-01-02T00:00:00+00:00",
        ),
    ]

    with pytest.raises(ValueError, match="Duplicate"):
        factory.build(
            records,
            dataset_id="delta-test",
            version="1",
            source="unit-test",
        )


def test_factory_rejects_lookahead() -> None:
    factory = DatasetFactory()

    records = [
        _record(
            "future",
            "2026-01-01T00:00:00+00:00",
            effective_at="2026-01-02T00:00:00+00:00",
        )
    ]

    with pytest.raises(ValueError, match="leakage"):
        factory.build(
            records,
            dataset_id="delta-test",
            version="1",
            source="unit-test",
        )


def test_non_strict_audit_preserves_failure_information() -> None:
    result = audit_dataset(
        [
            _record(
                "future",
                "2026-01-01T00:00:00+00:00",
                effective_at="2026-01-02T00:00:00+00:00",
            )
        ],
        dataset_id="delta-test",
        version="1",
        source="unit-test",
    )

    assert result.passed is False
    assert result.leakage_violations == 1
    assert result.record_count == 1


def test_jsonl_factory(tmp_path) -> None:
    path = tmp_path / "dataset.jsonl"

    rows = [
        _record(
            "a",
            "2026-01-01T00:00:00+00:00",
        ),
        _record(
            "b",
            "2026-01-02T00:00:00+00:00",
        ),
    ]

    path.write_text(
        "\n".join(
            json.dumps(row)
            for row in rows
        ),
        encoding="utf-8",
    )

    artifact = DatasetFactory().build_from_jsonl(
        path,
        dataset_id="delta-jsonl",
        version="1",
    )

    assert artifact.record_count == 2
    assert len(artifact.dataset_hash) == 64
    assert artifact.leakage_passed is True