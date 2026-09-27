from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Sequence


@dataclass(frozen=True, slots=True)
class ProtectedFailure:

    failure_id: str
    description: str
    test: Callable[[], bool]


@dataclass(frozen=True, slots=True)
class RegressionResult:

    failure_id: str
    passed: bool
    description: str


class ProtectedFailureSuite:

    def __init__(
        self,
        failures: Sequence[ProtectedFailure],
    ):
        self.failures = tuple(failures)

    def run(
        self,
    ) -> tuple[RegressionResult, ...]:

        results = []

        for failure in self.failures:

            try:
                passed = bool(
                    failure.test()
                )
            except Exception:
                passed = False

            results.append(
                RegressionResult(
                    failure.failure_id,
                    passed,
                    failure.description,
                )
            )

        return tuple(results)

    @staticmethod
    def certified(
        results: Sequence[RegressionResult],
    ) -> bool:

        return bool(results) and all(
            result.passed
            for result in results
        )