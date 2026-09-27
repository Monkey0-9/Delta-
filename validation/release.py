from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ReleaseStatus(StrEnum):
    CERTIFIED = "certified"
    BLOCKED = "blocked"


@dataclass(frozen=True, slots=True)
class ReleaseEvidence:
    unit_passed: bool
    integration_passed: bool
    replay_deterministic: bool
    chaos_passed: bool
    security_passed: bool
    perf_within_budget: bool
    protected_failures_passed: bool
    stress_passed: bool = True
    finbench_passed: bool = True
    walkforward_passed: bool = True


@dataclass(frozen=True, slots=True)
class ReleaseDecision:
    status: ReleaseStatus
    reasons: tuple[str, ...]


REQUIRED_CHECKS: tuple[str, ...] = (
    "unit_passed",
    "integration_passed",
    "replay_deterministic",
    "chaos_passed",
    "security_passed",
    "perf_within_budget",
    "protected_failures_passed",
    "stress_passed",
    "finbench_passed",
    "walkforward_passed",
)


def certify_release(evidence: ReleaseEvidence) -> ReleaseDecision:
    """Release certification gate: ALL checks must pass (fail-closed)."""
    failed = tuple(c for c in REQUIRED_CHECKS if not getattr(evidence, c))
    if failed:
        return ReleaseDecision(
            ReleaseStatus.BLOCKED,
            tuple(f"blocked: {c}" for c in failed),
        )
    return ReleaseDecision(ReleaseStatus.CERTIFIED, ("all gates passed",))
