from __future__ import annotations

from dataclasses import dataclass

from finance_model.datasets.drift import DriftReport
from finance_model.datasets.quality_gate import QualityReport


@dataclass(frozen=True, slots=True)
class ResearchDataQualityResult:
    quality: QualityReport
    drift: DriftReport

    @property
    def passed_quality(self) -> bool:
        return self.quality.passed

    @property
    def detected_drift(self) -> tuple[str, ...]:
        return self.drift.drifted_fields

    @property
    def passed(self) -> bool:
        return self.quality.passed