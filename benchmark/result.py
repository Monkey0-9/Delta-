from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BenchmarkResult:
    name: str
    workload_size: int
    iterations: int
    elapsed_seconds: float
    total_operations: int
    operations_per_second: float
    elements_per_second: float
    p50_seconds: float
    p95_seconds: float
    p99_seconds: float
    p999_seconds: float = 0.0
    correctness_hash: str = ""
    dataset_hash: str = ""
    commit: str = ""
    hardware: str = ""
    python_version: str = ""
    timestamp_utc: str = ""

    @property
    def speedup_against(
        self,
    ) -> float:
        raise AttributeError(
            "Use compare() with another BenchmarkResult."
        )


def compare(
    baseline: BenchmarkResult,
    candidate: BenchmarkResult,
) -> float:
    if candidate.elapsed_seconds <= 0:
        raise ValueError(
            "Candidate elapsed time must be positive."
        )

    return (
        baseline.elapsed_seconds
        / candidate.elapsed_seconds
    )