from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True, slots=True)
class Ablation:

    name: str
    run: Callable[[], float]


@dataclass(frozen=True, slots=True)
class AblationResult:

    name: str
    score: float


@dataclass(frozen=True, slots=True)
class ContributionReport:

    full_score: float
    contributions: tuple[AblationResult, ...]
    passed: bool
    details: tuple[str, ...]


class AblationRunner:

    def run(
        self,
        experiments: list[Ablation],
    ) -> tuple[AblationResult, ...]:

        return tuple(
            AblationResult(
                experiment.name,
                experiment.run(),
            )
            for experiment in experiments
        )

    def compare(
        self,
        full: Ablation,
        ablated: list[Ablation],
        *,
        min_contribution: float = 0.0,
    ) -> ContributionReport:
        """Full-system vs component-removed runs.

        contribution(component) = full_score - ablated_score.
        Positive contribution means the component helps.
        Passes when every ablated run scores no better than full
        beyond -min_contribution tolerance.
        """
        full_score = full.run()
        results = self.run(ablated)
        details: list[str] = []
        ok = True
        for res in results:
            contrib = full_score - res.score
            details.append(f"{res.name}: contribution={contrib:.6f}")
            if contrib < -min_contribution:
                ok = False
        return ContributionReport(full_score, results, ok, tuple(details))