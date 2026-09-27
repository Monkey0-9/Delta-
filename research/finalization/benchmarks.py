from __future__ import annotations

import statistics
import subprocess
import time
from typing import Callable

from .contracts import BenchmarkResult


def benchmark_callable(
    name: str,
    implementation: str,
    function: Callable[[], object],
    iterations: int = 100,
) -> BenchmarkResult:

    if iterations <= 0:
        raise ValueError(
            "iterations must be positive"
        )

    timings = []

    for _ in range(iterations):

        start = time.perf_counter()

        function()

        elapsed = (
            time.perf_counter()
            - start
        )

        timings.append(elapsed)

    elapsed_total = sum(timings)

    ops = (
        iterations / elapsed_total
        if elapsed_total > 0
        else float("inf")
    )

    return BenchmarkResult(
        name=name,
        implementation=implementation,
        iterations=iterations,
        elapsed_seconds=elapsed_total,
        operations_per_second=ops,
        measured=True,
        notes=(
            f"median_call_seconds="
            f"{statistics.median(timings):.12g}"
        ),
    )


def run_command_benchmark(
    name: str,
    command: list[str],
    iterations: int = 5,
) -> BenchmarkResult:

    timings = []

    for _ in range(iterations):

        start = time.perf_counter()

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
        )

        elapsed = (
            time.perf_counter()
            - start
        )

        if result.returncode != 0:
            raise RuntimeError(
                "Benchmark command failed:\n"
                + result.stderr
            )

        timings.append(elapsed)

    total = sum(timings)

    return BenchmarkResult(
        name=name,
        implementation="external_command",
        iterations=iterations,
        elapsed_seconds=total,
        operations_per_second=(
            iterations / total
            if total > 0
            else float("inf")
        ),
        measured=True,
    )


def rust_workspace_test() -> BenchmarkResult:

    return run_command_benchmark(
        name="rust_workspace",
        command=[
            "cargo",
            "test",
            "--workspace",
        ],
        iterations=1,
    )


def rust_workspace_bench_compile() -> BenchmarkResult:

    return run_command_benchmark(
        name="rust_bench_compile",
        command=[
            "cargo",
            "bench",
            "--workspace",
            "--no-run",
        ],
        iterations=1,
    )
