from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class BenchmarkDimension(StrEnum):
    FINANCIAL_KNOWLEDGE = "financial_knowledge"
    NUMERICAL_REASONING = "numerical_reasoning"
    MARKET_REASONING = "market_reasoning"
    MACRO_REASONING = "macro_reasoning"
    PORTFOLIO_REASONING = "portfolio_reasoning"
    RISK_REASONING = "risk_reasoning"
    TOOL_SELECTION = "tool_selection"
    TOOL_CORRECTNESS = "tool_correctness"
    EVIDENCE_GROUNDING = "evidence_grounding"
    UNCERTAINTY = "uncertainty"
    ABSTENTION = "abstention"
    ADVERSARIAL_ROBUSTNESS = "adversarial_robustness"


@dataclass(frozen=True, slots=True)
class BenchmarkScore:
    dimension: BenchmarkDimension
    score: float
    sample_count: int

    def validate(self) -> None:

        if not 0.0 <= self.score <= 1.0:
            raise ValueError(
                f"Invalid score for "
                f"{self.dimension}: "
                f"{self.score}"
            )

        if self.sample_count <= 0:
            raise ValueError(
                "sample_count must be positive"
            )


@dataclass(frozen=True, slots=True)
class BenchmarkReport:

    model_id: str
    scores: tuple[BenchmarkScore, ...]

    @property
    def mean_score(self) -> float:

        if not self.scores:
            return 0.0

        return sum(
            score.score
            for score in self.scores
        ) / len(self.scores)

    @property
    def passed(self) -> bool:

        return all(
            score.score >= 0.70
            for score in self.scores
        )