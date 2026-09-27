from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class PromotionStatus(StrEnum):
    REJECTED = "rejected"
    SHADOW = "shadow"
    CANDIDATE = "candidate"
    PROMOTED = "promoted"


@dataclass(frozen=True, slots=True)
class ValidationEvidence:
    walk_forward_passed: bool
    out_of_sample_passed: bool
    stress_passed: bool
    regression_passed: bool
    protected_failures_passed: bool


@dataclass(frozen=True, slots=True)
class PromotionDecision:
    status: PromotionStatus
    reason: str


class AdaptationGate:

    def evaluate(
        self,
        evidence: ValidationEvidence,
    ) -> PromotionDecision:

        if not evidence.regression_passed:
            return PromotionDecision(
                PromotionStatus.REJECTED,
                "Regression validation failed.",
            )

        if not evidence.protected_failures_passed:
            return PromotionDecision(
                PromotionStatus.REJECTED,
                "Protected failure regression failed.",
            )

        if not evidence.walk_forward_passed:
            return PromotionDecision(
                PromotionStatus.REJECTED,
                "Walk-forward validation failed.",
            )

        if not evidence.out_of_sample_passed:
            return PromotionDecision(
                PromotionStatus.REJECTED,
                "Out-of-sample validation failed.",
            )

        if not evidence.stress_passed:
            return PromotionDecision(
                PromotionStatus.REJECTED,
                "Stress validation failed.",
            )

        return PromotionDecision(
            PromotionStatus.CANDIDATE,
            "Candidate passed offline validation.",
        )