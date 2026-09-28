"""DELTA native performance benchmark — Python vs C vs C++ vs Rust.

Replaces the stale 2024 script (which contained C++ `::` syntax that is not
valid Python and imported modules that do not exist). Every workload here
dispatches through the real `native.accel` / `native.lob` / `native.rust_bridge`
APIs with NumPy-fallback parity, so results are honest on any machine:
backend name + ops/sec + p50/p99 per kernel, saved as JSON evidence.

Usage: python benchmark_performance.py [--iterations N] [--out FILE]
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

import numpy as np


def _timed(fn, iterations: int, warmup: int = 3) -> dict:
    for _ in range(warmup):
        fn()
    samples = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - t0) * 1e6)  # us
    samples.sort()
    n = len(samples)
    pct = lambda p: samples[min(n - 1, int(n * p))]
    return {"p50_us": round(pct(0.50), 3), "p99_us": round(pct(0.99), 3),
            "max_us": round(samples[-1], 3), "mean_us": round(statistics.mean(samples), 3)}


def bench_feature_kernels(n: int = 100_000) -> dict:
    from native import accel
    rng = np.random.default_rng(7)
    px = 100.0 * np.exp(np.cumsum(rng.normal(0.0005, 0.015, n)))
    out = {"backend": accel.backend(), "n": n}
    r = _timed(lambda: accel.returns(px), 20)
    out["returns"] = r
    m = _timed(lambda: accel.roll_mean_std(px, 20), 20)
    out["roll_mean_std_w20"] = m
    s = _timed(lambda: accel.rsi(px, 14), 20)
    out["rsi_w14"] = s
    x = rng.normal(0, 1, 500)
    y = rng.normal(0, 1, 500)
    ic = _timed(lambda: accel.spearman_ic(x, y), 20)
    out["spearman_ic_n500"] = ic
    q = rng.integers(1, 1000, n).astype(np.uint64)
    p = rng.integers(90, 110, n).astype(np.uint64)
    out["checksum"] = _timed(lambda: accel.checksum_u64(q), 20)
    out["exposure"] = _timed(lambda: accel.exposure(q, p), 20)
    asks = np.full(50, 1_000, dtype=np.uint64)
    out["match_orders"] = _timed(lambda: accel.match_orders(25_000, asks), 50)
    prices = np.linspace(99.5, 100.5, 50)
    qtys = np.full(50, 1_000, dtype=np.uint64)
    out["sweep_asks"] = _timed(lambda: accel.sweep_asks(25_000, prices, qtys), 50)
    return out


def bench_cpp_matcher(n_orders: int = 20_000) -> dict:
    from decimal import Decimal
    from native.lob import NativeMatcher, available
    if not available():
        return {"backend": "cpp-lob", "status": "not_available"}
    m = NativeMatcher()
    try:
        lat = []
        base = Decimal("100.00")
        for i in range(n_orders):
            side = "buy" if i % 2 == 0 else "sell"
            px = base + Decimal("0.01") * (i % 20 - 10)
            t0 = time.perf_counter()
            m.add(f"bench-{i}", side, px, Decimal("10"))
            lat.append((time.perf_counter() - t0) * 1e6)
        lat.sort()
        n = len(lat)
        pct = lambda p: lat[min(n - 1, int(n * p))]
        wall_s = None
        return {"backend": "cpp-lob", "orders": n_orders,
                "p50_us": round(pct(0.50), 3), "p99_us": round(pct(0.99), 3),
                "max_us": round(lat[-1], 3), "wall_note": wall_s}
    finally:
        m.close()


def bench_rust_bridge(n: int = 50_000) -> dict:
    from native.rust_bridge import RustBridge
    b = RustBridge()
    vals = list(range(n))
    out = {"available": b.is_available()}
    out["checksum"] = _timed(lambda: b.checksum_u64(vals), 10)
    out["normalize_dedup"] = _timed(lambda: b.normalize_dedup(vals * 1), 10)
    return out


def bench_python_baseline(n: int = 100_000) -> dict:
    from benchmark.native_parity import py_checksum, py_match_orders, py_feature_returns
    from decimal import Decimal
    vals = tuple(range(n))
    asks = tuple([1000] * 50)
    prices = tuple(Decimal("100") + Decimal("0.01") * (i % 20 - 10) for i in range(500))
    return {
        "checksum": _timed(lambda: py_checksum(vals), 5),
        "match_orders": _timed(lambda: py_match_orders(25_000, asks), 20),
        "feature_returns_n500": _timed(lambda: py_feature_returns(prices), 10),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="DELTA native performance benchmark")
    ap.add_argument("--iterations", type=int, default=100_000)
    ap.add_argument("--out", default="artifacts/benchmark_native.json")
    args = ap.parse_args()
    results = {
        "python_baseline": bench_python_baseline(args.iterations),
        "feature_kernels": bench_feature_kernels(args.iterations),
        "cpp_matcher": bench_cpp_matcher(20_000),
        "rust_bridge": bench_rust_bridge(50_000),
    }
    # Speedup evidence: native checksum vs pure-Python checksum (same workload size class)
    try:
        py = results["python_baseline"]["checksum"]["mean_us"]
        nat = results["feature_kernels"]["checksum"]["mean_us"]
        results["speedup_checksum_vs_python"] = round(py / max(nat, 1e-9), 2)
    except KeyError:
        pass
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, indent=2, sort_keys=True))
    print(json.dumps(results, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
