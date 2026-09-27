from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True, slots=True)
class SecurityTest:

    name: str
    check: Callable[[], bool]


class SecuritySuite:

    def __init__(
        self,
        tests: list[SecurityTest],
    ):
        self.tests = tuple(tests)

    def run(self) -> dict:

        results = {}

        for test in self.tests:

            try:
                results[test.name] = bool(
                    test.check()
                )
            except Exception:
                results[test.name] = False

        return {
            "tests": results,
            "passed": all(
                results.values()
            ) if results else False,
        }