from __future__ import annotations

import time
import urllib.request


def measure_http(
    url: str,
    iterations: int = 20,
    timeout: float = 10.0,
) -> dict:

    samples = []
    failures = 0

    for _ in range(iterations):

        start = time.perf_counter_ns()

        try:

            with urllib.request.urlopen(
                url,
                timeout=timeout,
            ) as response:

                response.read()

            elapsed = (
                time.perf_counter_ns()
                - start
            )

            samples.append(elapsed)

        except Exception:
            failures += 1

    if not samples:
        return {
            "measured": False,
            "failures": failures,
            "reason": "No successful requests.",
        }

    samples.sort()

    def pct(q: float) -> int:
        index = int(
            q * (len(samples) - 1)
        )
        return samples[index]

    return {
        "measured": True,
        "iterations": iterations,
        "successful": len(samples),
        "failures": failures,
        "median_ns": pct(0.50),
        "p95_ns": pct(0.95),
        "p99_ns": pct(0.99),
        "max_ns": samples[-1],
    }
