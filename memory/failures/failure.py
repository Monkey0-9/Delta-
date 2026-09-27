from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID, uuid4

from core.domain.timestamp import ensure_utc, utc_now


class FailureType(StrEnum):
    """Canonical failure vocabulary (mirrors core.contracts.canonical.FailureCategory).

    Single source of truth: core.contracts.canonical.FailureCategory.
    """

    NO_FAILURE = "no_failure"
    MODEL_ERROR = "model_error"
    REGIME_ERROR = "regime_error"
    DATA_ERROR = "data_error"
    EVENT_ERROR = "event_error"
    RISK_ERROR = "risk_error"
    EXECUTION_ERROR = "execution_error"
    LIQUIDITY_ERROR = "liquidity_error"
    PORTFOLIO_ERROR = "portfolio_error"
    DECISION_ERROR = "decision_error"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class FailureRecord:
    decision_id: str
    failure_type: FailureType

    expected_outcome: Decimal
    actual_outcome: Decimal
    error_magnitude: Decimal

    root_cause: str
    lesson: str

    confidence: Decimal

    model_version: str
    regime: str

    failure_id: UUID = field(default_factory=uuid4)
    timestamp: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        if not self.decision_id:
            raise ValueError("decision_id cannot be empty.")

        if not Decimal("0") <= self.confidence <= Decimal("1"):
            raise ValueError("confidence must be between 0 and 1.")

        if not self.root_cause.strip():
            raise ValueError("root_cause cannot be empty.")

        if not self.lesson.strip():
            raise ValueError("lesson cannot be empty.")

        object.__setattr__(
            self,
            "timestamp",
            ensure_utc(self.timestamp),
        )