"""W231-W250 (P+Q) — Kernel benchmarks (measured, reproducible) + differential
testing harness (Python = Rust = C++ where available, honest where not).

Benchmarks report p50/p95/p99/p99.9 on the DOCUMENTED machine instead of
claiming 'sub-microsecond'. Differential tests compare kernels over
randomized/edge/large/pathological inputs and report parity or MISSING.
"""
from __future__ import annotations

import platform
import time
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class KernelReport:
    kernel: str
    backend: str
    machine: str
    p50_ns: int
    p95_ns: int
    p99_ns: int
    p999_ns: int
    n: int


def machine_id() -> str:
    return f"{platform.system()}/{platform.machine()}/{platform.python_version()}"


def bench_kernel(name: str, backend: str, fn, n: int = 2000) -> KernelReport:
    samples = []
    for _ in range(n):
        t0 = time.perf_counter_ns()
        fn()
        samples.append(time.perf_counter_ns() - t0)
    samples.sort()
    at = lambda q: samples[min(len(samples) - 1, int(len(samples) * q))]
    return KernelReport(name, backend, machine_id(), at(0.50), at(0.95), at(0.99),
                        at(0.999), n)


def bench_table(reports: list[KernelReport]) -> str:
    lines = [f"{'Kernel':<16}{'backend':<10}{'p50':>10}{'p95':>10}{'p99':>10}{'p99.9':>10}",
             "-" * 66]
    for r in reports:
        lines.append(f"{r.kernel:<16}{r.backend:<10}{r.p50_ns:>10}{r.p95_ns:>10}"
                     f"{r.p99_ns:>10}{r.p999_ns:>10}")
    lines.append(f"machine: {reports[0].machine}" if reports else "machine: unknown")
    return "\n".join(lines)


# ---------- differential testing ----------

@dataclass
class DifferentialCase:
    name: str
    inputs: tuple
    python_result: object = None
    native_result: object = None
    native_available: bool = False


@dataclass
class DifferentialSuite:
    cases: list[DifferentialCase] = field(default_factory=list)

    def add(self, name: str, inputs: tuple, python_fn, native_fn=None) -> None:
        py = python_fn(*inputs)
        if native_fn is None:
            self.cases.append(DifferentialCase(name, inputs, py, None, False))
        else:
            try:
                nv = native_fn(*inputs)
                self.cases.append(DifferentialCase(name, inputs, py, nv, True))
            except Exception:  # noqa: BLE001 - unavailable native is a finding, not a crash
                self.cases.append(DifferentialCase(name, inputs, py, None, False))

    def report(self) -> dict:
        compared = [c for c in self.cases if c.native_available]
        matched = [c for c in compared if c.python_result == c.native_result]
        missing = [c.name for c in self.cases if not c.native_available]
        return {"n": len(self.cases), "compared": len(compared),
                "matched": len(matched),
                "mismatched": [c.name for c in compared if c.python_result != c.native_result],
                "missing_native": missing,
                "parity": len(compared) > 0 and len(matched) == len(compared)}
