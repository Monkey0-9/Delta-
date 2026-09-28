"""W140/W141 — Rust/perf + p99 benchmark suite (measured latency budgets).

Deterministic in-process latency measurement: runs fn, records per-call
ns timings, reports p50/p99/p99.9/p99.99 + budget verdict. Uses perf_counter_ns.
"""
from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LatencyReport:
    n: int
    p50_ns: int
    p99_ns: int
    p999_ns: int
    p9999_ns: int
    mean_ns: int
    within_budget: bool
    budget_ns: int


def _pct(sorted_ns: list[int], q: float) -> int:
    if not sorted_ns:
        return 0
    idx = min(len(sorted_ns) - 1, int(len(sorted_ns) * q))
    return sorted_ns[idx]


def measure_latency(fn, calls: int = 1000, budget_ns: int = 100_000) -> LatencyReport:
    samples: list[int] = []
    for _ in range(calls):
        t0 = time.perf_counter_ns()
        fn()
        samples.append(time.perf_counter_ns() - t0)
    samples.sort()
    mean = int(sum(samples) / len(samples))
    return LatencyReport(
        len(samples), _pct(samples, 0.50), _pct(samples, 0.99),
        _pct(samples, 0.999), _pct(samples, 0.9999), mean,
        _pct(samples, 0.99) <= budget_ns, budget_ns,
    )
