from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class PromotionStatus(str, Enum):
    CANDIDATE = "CANDIDATE"
    VALIDATING = "VALIDATING"
    SHADOW = "SHADOW"
    PROMOTED = "PROMOTED"
    REJECTED = "REJECTED"


@dataclass(frozen=True, slots=True)
class Candidate:

    candidate_id: str
    model_version: str
    strategy_version: str
    status: PromotionStatus


@dataclass(frozen=True, slots=True)
class ValidationEvidence:

    candidate_id: str
    oos_passed: bool
    stress_passed: bool
    regression_passed: bool
    calibration_passed: bool


class AdaptationController:

    def validate(
        self,
        candidate: Candidate,
        evidence: ValidationEvidence,
    ) -> Candidate:

        if (
            evidence.candidate_id
            != candidate.candidate_id
        ):
            raise ValueError(
                "candidate mismatch"
            )

        passed = all(
            (
                evidence.oos_passed,
                evidence.stress_passed,
                evidence.regression_passed,
                evidence.calibration_passed,
            )
        )

        if not passed:
            return Candidate(
                candidate.candidate_id,
                candidate.model_version,
                candidate.strategy_version,
                PromotionStatus.REJECTED,
            )

        return Candidate(
            candidate.candidate_id,
            candidate.model_version,
            candidate.strategy_version,
            PromotionStatus.SHADOW,
        )

    def promote(
        self,
        candidate: Candidate,
        *,
        explicit_approval: bool,
    ) -> Candidate:

        if candidate.status != PromotionStatus.SHADOW:
            raise ValueError(
                "only shadow candidates can be promoted"
            )

        if not explicit_approval:
            raise PermissionError(
                "explicit promotion approval required"
            )

        return Candidate(
            candidate.candidate_id,
            candidate.model_version,
            candidate.strategy_version,
            PromotionStatus.PROMOTED,
        )