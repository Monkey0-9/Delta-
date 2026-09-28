"""W101-W180 microstructure benchmark: throughput + p50/p95/p99 latency evidence."""
from __future__ import annotations

import time
from decimal import Decimal

from simulation.l2_engine import L2Engine


def bench_l2_engine(n_orders: int = 20_000, seed: int = 7) -> dict:
    engine = L2Engine(seed=seed)
    base = Decimal("100.00")
    latencies: list[float] = []
    t0 = time.perf_counter()
    for i in range(n_orders):
        side = "buy" if i % 2 == 0 else "sell"
        px = base + Decimal("0.01") * (i % 20 - 10)
        t1 = time.perf_counter()
        engine.add(f"bench-{i}", side, px, Decimal("10"), latency_ns=50_000)
        engine.step_until(engine._ns + 200_000)
        latencies.append((time.perf_counter() - t1) * 1e6)  # us per order path
    wall = time.perf_counter() - t0
    latencies.sort()
    def pct(p: float) -> float:
        return latencies[min(len(latencies) - 1, int(len(latencies) * p))]
    return {
        "engine": "l2-engine-v1",
        "orders": n_orders,
        "events": len(engine.events),
        "fills": len(engine.fills),
        "events_per_sec": round(len(engine.events) / wall, 1) if wall > 0 else 0.0,
        "orders_per_sec": round(n_orders / wall, 1) if wall > 0 else 0.0,
        "latency_us": {"p50": round(pct(0.50), 2), "p95": round(pct(0.95), 2),
                       "p99": round(pct(0.99), 2), "max": round(latencies[-1], 2)},
        "deterministic_seed": seed,
    }


if __name__ == "__main__":
    import json
    print(json.dumps(bench_l2_engine(), indent=2))
