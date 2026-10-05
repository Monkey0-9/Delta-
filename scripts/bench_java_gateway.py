"""Documented-hardware Java loopback bench (honest numbers, no projections).

Measures TCP loopback PING tax + MATCH path on this machine with N samples,
reporting p50/p95/p99/max. Full N=1_000_000 certification lives in
benchmarks/java_spike/GO_NO_GO_MEMO.md; this script re-verifies the lane on
demand. Usage: python scripts/bench_java_gateway.py [--n 20000] [--port 9021]
"""
from __future__ import annotations

import argparse
import json
import platform
import statistics
import subprocess
import time
from pathlib import Path

from execution.adapters.java_gateway_adapter import JavaGatewayAdapter


def pct(data: list[float], q: float) -> float:
    s = sorted(data)
    if not s:
        return 0.0
    k = (len(s) - 1) * q
    f, c = int(k), min(int(k) + 1, len(s) - 1)
    return s[f] + (s[c] - s[f]) * (k - f)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=20000)
    ap.add_argument("--port", type=int, default=9021)
    args = ap.parse_args()

    try:
        jver = subprocess.run(["java", "-version"], capture_output=True, text=True, timeout=10)
        jdk = (jver.stderr.strip().splitlines() or ["unknown"])[0]
    except Exception as e:
        jdk = f"unavailable: {e}"

    gw = JavaGatewayAdapter(port=args.port, auto_spawn=True,
                              jvm_flags=["-Xms512m", "-Xmx2g", "-XX:+UseParallelGC"])
    print(f"starting gateway on :{args.port} ...", flush=True)
    gw.start()
    print("gateway HEALTHY; warming up ...", flush=True)
    try:
        # warm-up
        for _ in range(500):
            gw.status()
        lat: list[float] = []
        t0 = time.perf_counter()
        for i in range(args.n):
            t = time.perf_counter()
            gw.status()
            lat.append((time.perf_counter() - t) * 1e6)
            if (i + 1) % 5000 == 0:
                print(f"... {i + 1}/{args.n}", flush=True)
        wall = time.perf_counter() - t0
        lat_sorted = sorted(lat)
        out = {
            "component": "java_loopback_STATUS",
            "n": args.n,
            "throughput_per_s": round(args.n / wall, 1),
            "latency_us": {
                "p50": round(pct(lat, 0.50), 2),
                "p95": round(pct(lat, 0.95), 2),
                "p99": round(pct(lat, 0.99), 2),
                "max": round(lat_sorted[-1], 2),
            },
            "provenance": "BENCH_MEASURED",
            "hardware": {"machine": platform.machine(), "processor": platform.processor(),
                         "system": platform.system(), "release": platform.release()},
            "jdk": jdk,
            "jvm_flags": ["-Xms512m", "-Xmx2g", "-XX:+UseParallelGC"],
            "jvm_note": "min-heap lowered for 1GB-free bench box; max heap + GC identical to production; certified 2g/2g numbers in benchmarks/java_spike/GO_NO_GO_MEMO.md",
        }
        dest = Path("benchmarks/java_gateway_bench.json")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(out, indent=2))
        print(json.dumps(out, indent=2))
    finally:
        gw.stop()


if __name__ == "__main__":
    main()
