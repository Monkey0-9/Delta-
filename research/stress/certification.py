from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class StressResult:

    scenario: str
    return_value: float
    max_loss: float
    survived: bool


class StressCertification:

    def certify(
        self,
        results: list[StressResult],
        maximum_loss: float,
    ) -> bool:

        if not results:
            return False

        return all(
            result.survived
            and result.max_loss
            >= maximum_loss
            for result in results
        )