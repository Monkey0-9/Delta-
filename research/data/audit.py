from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from finance_model.datasets.factory import DatasetArtifact
from finance_model.datasets.factory import DatasetFactory


@dataclass(frozen=True, slots=True)
class DatasetAuditResult:
    dataset_id: str
    version: str
    record_count: int
    dataset_hash: str
    passed: bool
    leakage_violations: int


def audit_dataset(
    records: Iterable[dict[str, object]],
    *,
    dataset_id: str,
    version: str,
    source: str,
) -> DatasetAuditResult:
    artifact: DatasetArtifact = DatasetFactory(
        strict=False,
    ).build(
        records,
        dataset_id=dataset_id,
        version=version,
        source=source,
    )

    return DatasetAuditResult(
        dataset_id=artifact.dataset_id,
        version=artifact.version,
        record_count=artifact.record_count,
        dataset_hash=artifact.dataset_hash,
        passed=artifact.leakage_passed,
        leakage_violations=artifact.leakage_violations,
    )