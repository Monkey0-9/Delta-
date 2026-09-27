from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ResearchGateResult:
    name: str
    passed: bool
    reason: str


@dataclass(frozen=True, slots=True)
class ResearchGate:
    name: str
    minimum: float

    def evaluate(self, value: float) -> ResearchGateResult:
        passed = value >= self.minimum

        return ResearchGateResult(
            name=self.name,
            passed=passed,
            reason=(
                f"value={value:.6f}; "
                f"minimum={self.minimum:.6f}"
            ),
        )