from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from core.domain.timestamp import ensure_utc, utc_now


@dataclass(frozen=True, slots=True)
class Experience:
    decision_id: str
    instrument: str
    horizon: str
    regime: str

    prediction: Decimal
    actual: Decimal

    lesson: str
    failure_type: str

    model_version: str

    experience_id: UUID = field(default_factory=uuid4)
    timestamp: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        if not self.decision_id:
            raise ValueError("decision_id cannot be empty.")

        if not self.instrument:
            raise ValueError("instrument cannot be empty.")

        if not self.lesson:
            raise ValueError("lesson cannot be empty.")

        object.__setattr__(
            self,
            "timestamp",
            ensure_utc(self.timestamp),
        )