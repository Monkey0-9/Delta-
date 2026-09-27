from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from time import perf_counter
from typing import Callable, TypeVar

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class BenchmarkResult:
    name: str
    iterations: int
    elapsed_seconds: float
    operations_per_second: float
    result_digest: str
    p50_seconds: float = 0.0
    p95_seconds: float = 0.0
    p99_seconds: float = 0.0
    p999_seconds: float = 0.0
    correctness_hash: str = ""
    dataset_hash: str = ""
    commit: str = ""
    hardware: str = ""
    python_version: str = ""

    @property
    def average_latency_seconds(self) -> float:
        if self.iterations <= 0:
            return 0.0
        return self.elapsed_seconds / self.iterations


def deterministic_workload(size: int) -> tuple[Decimal, ...]:
    """
    Deterministic numerical workload.

    No random generator is used so benchmark results can be
    reproduced exactly.
    """
    if size < 1:
        raise ValueError("size must be positive")

    return tuple(
        Decimal((index * 7919) % 100000) / Decimal("100")
        for index in range(size)
    )


def checksum(values: tuple[Decimal, ...]) -> str:
    total = sum(values, Decimal("0"))
    return format(total, "f")


def benchmark(
    name: str,
    function: Callable[[], T],
    iterations: int = 1,
) -> BenchmarkResult:
    """Per-iteration timing with p50/p95/p99/p99.9 + provenance metadata."""
    import hashlib
    import platform
    import subprocess
    import sys

    if iterations < 1:
        raise ValueError("iterations must be positive")

    latencies: list[float] = []
    result: T | None = None
    for _ in range(iterations):
        start = perf_counter()
        result = function()
        latencies.append(perf_counter() - start)

    elapsed = sum(latencies)
    ops = iterations / elapsed if elapsed > 0 else float("inf")
    digest = str(result)
    ordered = sorted(latencies)

    def _pct(p: float) -> float:
        if not ordered:
            return 0.0
        k = min(len(ordered) - 1, int(p * len(ordered)))
        return ordered[k]

    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], text=True, timeout=10
        ).strip()
    except Exception:
        commit = "unknown"

    return BenchmarkResult(
        name=name,
        iterations=iterations,
        elapsed_seconds=elapsed,
        operations_per_second=ops,
        result_digest=digest,
        p50_seconds=_pct(0.50),
        p95_seconds=_pct(0.95),
        p99_seconds=_pct(0.99),
        p999_seconds=_pct(0.999),
        correctness_hash=hashlib.sha256(digest.encode()).hexdigest(),
        hardware=f"{platform.system()}/{platform.machine()}/{platform.processor()}",
        python_version=sys.version.split()[0],
        commit=commit,
    )