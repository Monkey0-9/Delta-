from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from datetime import datetime


class DatasetStage(StrEnum):
    DOMAIN = "domain"
    SFT = "sft"
    TOOL = "tool"
    PREFERENCE = "preference"
    REASONING = "reasoning"
    EVALUATION = "evaluation"


@dataclass(frozen=True, slots=True)
class Evidence:
    evidence_id: str
    source: str
    published_at: str
    effective_at: str
    text: str

    def effective_datetime(self) -> datetime:
        return datetime.fromisoformat(
            self.effective_at.replace(
                "Z",
                "+00:00",
            )
        )


@dataclass(frozen=True, slots=True)
class FinanceExample:
    example_id: str
    stage: DatasetStage

    prompt: str
    response: str

    evidence: tuple[Evidence, ...]

    decision_time: str

    asset: str | None = None
    horizon: str | None = None

    source_hash: str = ""
    dataset_version: str = ""

    availability_time: str | None = None

    def decision_datetime(self) -> datetime:
        return datetime.fromisoformat(
            self.decision_time.replace(
                "Z",
                "+00:00",
            )
        )

    def validate_temporal_integrity(self) -> None:
        decision_time = self.decision_datetime()

        if self.availability_time is not None:

            availability_time = datetime.fromisoformat(
                self.availability_time.replace(
                    "Z",
                    "+00:00",
                )
            )

            if availability_time > decision_time:
                raise ValueError(
                    "Availability time occurs "
                    "after decision time"
                )

        for evidence in self.evidence:

            if evidence.effective_datetime() > decision_time:
                raise ValueError(
                    "Look-ahead contamination detected: "
                    f"{evidence.evidence_id}"
                )