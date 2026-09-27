from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Callable


@dataclass(frozen=True, slots=True)
class PerfBudget:
    name: str
    max_seconds: float
    baseline_file: str = ""


@dataclass(frozen=True, slots=True)
class PerfResult:
    name: str
    elapsed_seconds: float
    passed: bool
    detail: str


def check_budget(budget: PerfBudget, fn: Callable[[], object]) -> PerfResult:
    start = perf_counter()
    fn()
    elapsed = perf_counter() - start
    passed = elapsed <= budget.max_seconds
    return PerfResult(
        budget.name, elapsed, passed,
        f"{elapsed:.4f}s vs budget {budget.max_seconds:.4f}s",
    )


def compare_with_baseline(
    result: PerfResult, baseline_file: str | Path
) -> tuple[bool, str]:
    """Fail-closed perf regression: candidate must be within 20% of baseline."""
    path = Path(baseline_file)
    if not path.exists():
        return True, "no baseline; recording candidate as new baseline"
    baseline = json.loads(path.read_text(encoding="utf-8"))
    allowed = float(baseline["elapsed_seconds"]) * 1.20
    if result.elapsed_seconds <= allowed:
        return True, f"{result.elapsed_seconds:.4f}s <= {allowed:.4f}s"
    return False, f"regression: {result.elapsed_seconds:.4f}s > {allowed:.4f}s"


def write_baseline(result: PerfResult, baseline_file: str | Path) -> None:
    path = Path(baseline_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"name": result.name, "elapsed_seconds": result.elapsed_seconds}),
        encoding="utf-8",
    )
