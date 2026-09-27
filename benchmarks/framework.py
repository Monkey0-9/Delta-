from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Callable


@dataclass(frozen=True, slots=True)
class BenchmarkResult:

    name: str
    iterations: int
    elapsed_seconds: float
    operations_per_second: float


class Benchmark:

    @staticmethod
    def run(
        name: str,
        operation: Callable[[], None],
        iterations: int,
    ) -> BenchmarkResult:

        if iterations <= 0:
            raise ValueError(
                "iterations must be positive"
            )

        for _ in range(
            min(100, iterations)
        ):
            operation()

        start = perf_counter()

        for _ in range(iterations):
            operation()

        elapsed = (
            perf_counter()
            - start
        )

        return BenchmarkResult(
            name,
            iterations,
            elapsed,
            iterations / elapsed
            if elapsed
            else float("inf"),
        )