from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class EvaluationResult:
    metric: str
    score: float
    passed: bool
    threshold: float


@dataclass(frozen=True, slots=True)
class ModelEvaluation:

    model_id: str
    results: tuple[EvaluationResult, ...]

    @property
    def passed(self) -> bool:
        return all(result.passed for result in self.results)

    def failed_metrics(self) -> tuple[str, ...]:
        return tuple(
            result.metric
            for result in self.results
            if not result.passed
        )