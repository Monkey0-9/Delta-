"""Production SLO gates: p50/p95/p99 latency budgets + error budget check.

Used by launch evidence and shadow promotion. Fail-closed: missing data
is a FAIL (no SLO proof without measurements).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SlotResult:
    slo: str
    status: str  # PASS | FAIL
    detail: str = ""


def check_latency_slo(latencies_us: tuple[float, ...], p50_max_us: float,
                      p95_max_us: float, p99_max_us: float, name: str = "order-path") -> SlotResult:
    if not latencies_us:
        return SlotResult(name, "FAIL", "no measurements.")
    ordered = sorted(latencies_us)

    def pct(p: float) -> float:
        return ordered[min(len(ordered) - 1, int(len(ordered) * p))]

    p50, p95, p99 = pct(0.50), pct(0.95), pct(0.99)
    ok = p50 <= p50_max_us and p95 <= p95_max_us and p99 <= p99_max_us
    return SlotResult(name, "PASS" if ok else "FAIL",
                      f"p50={p50:.1f}/{p50_max_us} p95={p95:.1f}/{p95_max_us} p99={p99:.1f}/{p99_max_us}us")


def check_error_budget(failures: int, total: int, budget: float = 0.0001,
                       name: str = "launch") -> SlotResult:
    if total <= 0:
        return SlotResult(name, "FAIL", "no trials.")
    rate = failures / total
    return SlotResult(name, "PASS" if rate <= budget else "FAIL",
                      f"error_rate={rate:.6f} budget={budget}.")
