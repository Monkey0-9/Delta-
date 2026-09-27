from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class DecisionDisposition(StrEnum):
    ACCEPT = "ACCEPT"
    REVIEW = "REVIEW"
    ABSTAIN = "ABSTAIN"


@dataclass(frozen=True, slots=True)
class ConfidenceAssessment:
    confidence: float
    minimum_confidence: float
    evidence_quality: float
    model_agreement: float

    @property
    def disposition(self) -> DecisionDisposition:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence outside [0,1]")

        if not 0.0 <= self.evidence_quality <= 1.0:
            raise ValueError(
                "evidence_quality outside [0,1]"
            )

        if not 0.0 <= self.model_agreement <= 1.0:
            raise ValueError(
                "model_agreement outside [0,1]"
            )

        if self.confidence < self.minimum_confidence:
            return DecisionDisposition.ABSTAIN

        if self.evidence_quality < 0.70:
            return DecisionDisposition.REVIEW

        if self.model_agreement < 0.60:
            return DecisionDisposition.REVIEW

        return DecisionDisposition.ACCEPT