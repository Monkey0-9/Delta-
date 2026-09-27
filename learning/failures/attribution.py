from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from core.contracts.canonical import FailureCategory


class FailureType(str, Enum):
    """Legacy learning/failures vocabulary — aliases of canonical FailureCategory.

    Single source of truth is core.contracts.canonical.FailureCategory.
    Retained for backward-compatible imports; .to_canonical() resolves.
    """
    PREDICTION = "PREDICTION"
    REGIME = "REGIME"
    DATA = "DATA"
    NEWS = "NEWS"
    RISK = "RISK"
    EXECUTION = "EXECUTION"
    RELATIONSHIP = "RELATIONSHIP"
    DECISION = "DECISION"
    UNKNOWN = "UNKNOWN"

    def to_canonical(self) -> FailureCategory:
        from core.contracts.canonical import normalize_failure_category

        return normalize_failure_category(self.value)


@dataclass(frozen=True, slots=True)
class FailureRecord:

    failure_id: str
    decision_id: str
    failure_type: FailureType
    expected: float
    realized: float
    magnitude: float
    root_cause: str
    evidence_ids: tuple[str, ...]


class FailureAttributor:

    def attribute(
        self,
        *,
        failure_id: str,
        decision_id: str,
        expected: float,
        realized: float,
        evidence_ids: tuple[str, ...],
        prediction_error_threshold: float = 0.05,
    ) -> FailureRecord:

        error = abs(
            realized - expected
        )

        if error <= prediction_error_threshold:
            failure_type = FailureType.UNKNOWN
            root = "within prediction tolerance"

        else:
            failure_type = FailureType.PREDICTION
            root = "forecast diverged from realization"

        return FailureRecord(
            failure_id=failure_id,
            decision_id=decision_id,
            failure_type=failure_type,
            expected=expected,
            realized=realized,
            magnitude=error,
            root_cause=root,
            evidence_ids=evidence_ids,
        )