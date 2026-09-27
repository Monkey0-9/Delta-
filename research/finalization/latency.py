from __future__ import annotations

import statistics
import time
from typing import Callable


def measure(
    function: Callable[[], object],
    iterations: int = 1_000,
) -> dict:

    samples = []

    for _ in range(iterations):

        start = time.perf_counter_ns()

        function()

        elapsed = (
            time.perf_counter_ns()
            - start
        )

        samples.append(elapsed)

    samples.sort()

    def percentile(q: float) -> float:
        index = int(
            q * (len(samples) - 1)
        )

        return samples[index]

    return {
        "iterations": iterations,
        "min_ns": samples[0],
        "median_ns": percentile(0.50),
        "p95_ns": percentile(0.95),
        "p99_ns": percentile(0.99),
        "p99_9_ns": percentile(0.999),
        "max_ns": samples[-1],
        "mean_ns": statistics.mean(
            samples
        ),
    }
