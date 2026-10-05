"""DELTA Institutional Comprehensive Empirical Benchmark Suite.

Executes genuine, measured benchmarks across all system layers:
1. Rust Native C-ABI vs NumPy vs Pandas
2. Canonical 12-Stage Quantitative Loop Latency
3. IPC & Micro-architecture Bridge Tax

Zero fake metrics, zero unmeasured claims. Everything is timed using
hardware-backed high-resolution monotonic clocks (perf_counter_ns).
"""
from __future__ import annotations

import collections
import gc
import os
import platform
import socket
import sys
import time
from dataclasses import dataclass

os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"

import numpy as np
import pandas as pd

from native import accel
from core.canonical_pipeline import (
    CanonicalInstitutionalPipeline,
    OrderSide,
    MarketRegime,
)


@dataclass(frozen=True, slots=True)
class TimingStats:
    name: str
    backend: str
    n_ops: int
    total_time_s: float
    throughput_ops_sec: float
    p50_us: float
    p95_us: float
    p99_us: float
    p999_us: float
    max_us: float


def measure_latencies(name: str, backend: str, fn, iterations: int = 1000) -> TimingStats:
    # Warmup
    for _ in range(max(5, iterations // 20)):
        fn()

    gc.collect()
    samples_ns = []
    t_start = time.perf_counter_ns()
    for _ in range(iterations):
        t0 = time.perf_counter_ns()
        fn()
        samples_ns.append(time.perf_counter_ns() - t0)
    total_ns = time.perf_counter_ns() - t_start

    samples_ns.sort()
    n = len(samples_ns)
    total_s = total_ns / 1e9
    throughput = n / total_s if total_s > 0 else 0

    p50 = samples_ns[int(n * 0.50)] / 1000.0
    p95 = samples_ns[int(n * 0.95)] / 1000.0
    p99 = samples_ns[int(n * 0.99)] / 1000.0
    p999 = samples_ns[min(n - 1, int(n * 0.999))] / 1000.0
    max_lat = samples_ns[-1] / 1000.0

    return TimingStats(
        name=name,
        backend=backend,
        n_ops=iterations,
        total_time_s=total_s,
        throughput_ops_sec=throughput,
        p50_us=p50,
        p95_us=p95,
        p99_us=p99,
        p999_us=p999,
        max_us=max_lat,
    )


def bench_native_kernels():
    print("=" * 80)
    print(f" 1. NATIVE KERNEL BENCHMARKS (Active Backend: {accel.backend().upper()})")
    print("=" * 80)
    results = []

    # 1. Wilder RSI (100,000 price ticks)
    n_ticks = 100_000
    prices = np.cumsum(np.random.normal(0, 1, n_ticks)) + 150.0

    stats_rsi_rust = measure_latencies(
        "RSI Wilder (100k ticks)",
        accel.backend(),
        lambda: accel.rsi(prices, 14),
        iterations=200,
    )
    results.append(stats_rsi_rust)

    stats_rsi_np = measure_latencies(
        "RSI Wilder (100k ticks)",
        "numpy",
        lambda: accel.np_rsi_wilder(prices, 14),
        iterations=200,
    )
    results.append(stats_rsi_np)

    # 2. Rolling Mean & Std (50,000 ticks, window 20)
    n_roll = 50_000
    roll_prices = np.random.normal(100, 5, n_roll)
    stats_roll_rust = measure_latencies(
        "Rolling Mean/Std (50k ticks)",
        accel.backend(),
        lambda: accel.roll_mean_std(roll_prices, 20),
        iterations=300,
    )
    results.append(stats_roll_rust)

    stats_roll_np = measure_latencies(
        "Rolling Mean/Std (50k ticks)",
        "numpy",
        lambda: accel.np_roll_mean_std(roll_prices, 20),
        iterations=300,
    )
    results.append(stats_roll_np)

    # 3. Spearman Rank Correlation (2,000 assets)
    rng = np.random.default_rng(42)
    x = rng.normal(0, 1, 2000)
    y = 0.5 * x + rng.normal(0, 1, 2000)

    stats_spearman_rust = measure_latencies(
        "Spearman IC (2,000 items)",
        accel.backend(),
        lambda: accel.spearman_ic(x, y),
        iterations=1000,
    )
    results.append(stats_spearman_rust)

    stats_spearman_pd = measure_latencies(
        "Spearman IC (2,000 items)",
        "pandas",
        lambda: pd.Series(x).corr(pd.Series(y), method="spearman"),
        iterations=200,
    )
    results.append(stats_spearman_pd)

    # 4. ERC (Equal Risk Contribution) sweep (10 assets)
    cov = np.cov(rng.normal(0, 1, (10, 200)))
    cov = np.ascontiguousarray(cov, dtype=np.float64)
    w = np.full(10, 0.1, dtype=np.float64)

    def numpy_erc_sweep(c: np.ndarray, weights: np.ndarray) -> float:
        sw = c @ weights
        pv = max(float(weights @ sw), 1e-18) ** 0.5
        n_assets = len(weights)
        target = pv / n_assets
        maxd = 0.0
        for i in range(n_assets):
            rc = max(weights[i] * sw[i] / pv, 1e-18)
            nw = weights[i] * min(max((target / rc) ** 0.5, 1e-3), 1e3)
            maxd = max(maxd, abs(nw - weights[i]))
            weights[i] = nw
        return maxd

    stats_erc_rust = measure_latencies(
        "ERC 1-Sweep (10x10 cov)",
        accel.backend(),
        lambda: accel.erc_sweep(cov, w.copy()),
        iterations=5000,
    )
    results.append(stats_erc_rust)

    stats_erc_np = measure_latencies(
        "ERC 1-Sweep (10x10 cov)",
        "numpy",
        lambda: numpy_erc_sweep(cov, w.copy()),
        iterations=5000,
    )
    results.append(stats_erc_np)

    # 5. LOB Ask Sweep (50,000 asks)
    ask_prices = np.linspace(100, 200, 50_000)
    ask_qty = np.full(50_000, 10, dtype=np.uint64)
    stats_sweep = measure_latencies(
        "LOB Sweep (50k depth levels)",
        "c_accel",
        lambda: accel.sweep_asks(25_000, ask_prices, ask_qty),
        iterations=1000,
    )
    results.append(stats_sweep)

    # Print Kernel Results Table
    print(f"{'Kernel Workload':<30} | {'Backend':<8} | {'p50 (µs)':>9} | {'p95 (µs)':>9} | {'p99 (µs)':>9} | {'Throughput':>15}")
    print("-" * 88)
    for r in results:
        print(f"{r.name:<30} | {r.backend:<8} | {r.p50_us:>9.2f} | {r.p95_us:>9.2f} | {r.p99_us:>9.2f} | {r.throughput_ops_sec:>12,.0f} op/s")

    return results


def bench_canonical_pipeline():
    print("\n" + "=" * 80)
    print(" 2. CANONICAL 12-STAGE QUANTITATIVE PIPELINE LATENCY")
    print("=" * 80)

    pipeline = CanonicalInstitutionalPipeline(initial_cash=1_000_000.0, venue="XNYS")
    spy_bars = pipeline.fetch_market_bars("SPY", n_bars=120)
    nvda_bars = pipeline.fetch_market_bars("NVDA", n_bars=120)

    stage_timings = collections.defaultdict(list)
    iterations = 200

    for i in range(iterations):
        # Stage 2: Technical Feature Extraction
        t0 = time.perf_counter_ns()
        stock_ind = pipeline.extract_features("NVDA", nvda_bars)
        mkt_ind = pipeline.extract_features("SPY", spy_bars)
        stage_timings["Stage 2: Technical Feature Extraction"].append(time.perf_counter_ns() - t0)

        # Stage 3: Alpha Generation & Neutralization
        t0 = time.perf_counter_ns()
        alpha = pipeline.generate_alpha(stock_ind, mkt_ind)
        stage_timings["Stage 3: Factor Alpha Generation"].append(time.perf_counter_ns() - t0)

        # Stage 4: Probabilistic Return Forecast
        t0 = time.perf_counter_ns()
        forecast = pipeline.forecast_return(alpha, stock_ind, horizon_days=5)
        stage_timings["Stage 4: Return Forecast Distribution"].append(time.perf_counter_ns() - t0)

        # Stage 5: Macro Factor Regime Classification
        t0 = time.perf_counter_ns()
        regime = pipeline.detect_regime(mkt_ind)
        stage_timings["Stage 5: Market Regime Classification"].append(time.perf_counter_ns() - t0)

        # Stage 6: Constrained Portfolio Optimization
        t0 = time.perf_counter_ns()
        alloc = pipeline.optimize_portfolio({"NVDA": forecast}, {"NVDA": stock_ind.price}, regime)
        stage_timings["Stage 6: Portfolio Allocation"].append(time.perf_counter_ns() - t0)

        # Stage 7: Pre-Trade Risk Firewall & Scenario Stress
        t0 = time.perf_counter_ns()
        approved, reason = pipeline.pre_trade_check("NVDA", OrderSide.BUY, 50.0, stock_ind.price)
        risk_metrics = pipeline.evaluate_risk({"NVDA": stock_ind.price})
        stage_timings["Stage 7: Pre-Trade Risk Firewall"].append(time.perf_counter_ns() - t0)

        # Stage 8: OMS Order State Machine & Idempotency
        t0 = time.perf_counter_ns()
        order = pipeline.create_order("NVDA", OrderSide.BUY, 50.0, stock_ind.price, f"bench-{i}")
        stage_timings["Stage 8: OMS Order Lifecycle"].append(time.perf_counter_ns() - t0)

        # Stage 9: Paper Execution & Almgren-Chriss Slippage
        t0 = time.perf_counter_ns()
        fill = pipeline.execute_order(order, stock_ind.price)
        stage_timings["Stage 9: Paper Matching & Slippage"].append(time.perf_counter_ns() - t0)

        # Stage 10: Three-Way Reconciliation
        t0 = time.perf_counter_ns()
        recon = pipeline.reconcile()
        stage_timings["Stage 10: Three-Way Reconciliation"].append(time.perf_counter_ns() - t0)

        # Stage 11: Cryptographic SHA-256 Chained Audit Trail
        t0 = time.perf_counter_ns()
        pipeline.log_audit("BENCHMARK_CYCLE", {"order_id": order.order_id if order else ""})
        stage_timings["Stage 11: Tamper-Evident SHA-256 Ledger"].append(time.perf_counter_ns() - t0)

    # Full End-to-End Cycle (in-memory execution loop)
    e2e_timings = []
    for i in range(iterations):
        t0 = time.perf_counter_ns()
        stock_ind = pipeline.extract_features("NVDA", nvda_bars)
        mkt_ind = pipeline.extract_features("SPY", spy_bars)
        alpha = pipeline.generate_alpha(stock_ind, mkt_ind)
        forecast = pipeline.forecast_return(alpha, stock_ind, horizon_days=5)
        regime = pipeline.detect_regime(mkt_ind)
        alloc = pipeline.optimize_portfolio({"NVDA": forecast}, {"NVDA": stock_ind.price}, regime)
        approved, reason = pipeline.pre_trade_check("NVDA", OrderSide.BUY, 10.0, stock_ind.price)
        order = pipeline.create_order("NVDA", OrderSide.BUY, 10.0, stock_ind.price, f"e2e-{i}")
        fill = pipeline.execute_order(order, stock_ind.price)
        recon = pipeline.reconcile()
        pipeline.log_audit("E2E_CYCLE", {"i": i})
        e2e_timings.append(time.perf_counter_ns() - t0)

    print(f"{'Pipeline Stage':<42} | {'p50 (µs)':>9} | {'p95 (µs)':>9} | {'p99 (µs)':>9} | {'Mean (µs)':>9}")
    print("-" * 88)

    for stage_name, timings in stage_timings.items():
        timings.sort()
        n = len(timings)
        p50 = timings[int(n * 0.50)] / 1000.0
        p95 = timings[int(n * 0.95)] / 1000.0
        p99 = timings[int(n * 0.99)] / 1000.0
        mean = (sum(timings) / n) / 1000.0
        print(f"{stage_name:<42} | {p50:>9.2f} | {p95:>9.2f} | {p99:>9.2f} | {mean:>9.2f}")

    e2e_timings.sort()
    n = len(e2e_timings)
    p50 = e2e_timings[int(n * 0.50)] / 1000.0
    p95 = e2e_timings[int(n * 0.95)] / 1000.0
    p99 = e2e_timings[int(n * 0.99)] / 1000.0
    mean = (sum(e2e_timings) / n) / 1000.0
    print("-" * 88)
    print(f"{'FULL CANONICAL 12-STAGE LOOP (E2E)':<42} | {p50:>9.2f} | {p95:>9.2f} | {p99:>9.2f} | {mean:>9.2f}")
    throughput = n / (sum(e2e_timings) / 1e9)
    print(f"Overall Decision Loop Throughput: {throughput:,.0f} decision cycles/sec")


def bench_ipc_and_bridge():
    print("\n" + "=" * 80)
    print(" 3. IPC & MICRO-ARCHITECTURE BRIDGE TAX")
    print("=" * 80)

    # Loopback TCP socket tax
    n = 10_000
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    port = server.getsockname()[1]

    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.connect(("127.0.0.1", port))
    conn, _ = server.accept()
    client.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

    latencies_ns = []
    for _ in range(n):
        t0 = time.perf_counter_ns()
        client.sendall(b'{"jsonrpc":"2.0","method":"ping","id":1}\n')
        msg = conn.recv(64)
        conn.sendall(b'{"jsonrpc":"2.0","result":"pong","id":1}\n')
        reply = client.recv(64)
        latencies_ns.append(time.perf_counter_ns() - t0)

    client.close()
    conn.close()
    server.close()

    latencies_ns.sort()
    p50 = latencies_ns[int(n * 0.50)] / 1000.0
    p95 = latencies_ns[int(n * 0.95)] / 1000.0
    p99 = latencies_ns[int(n * 0.99)] / 1000.0
    mean = (sum(latencies_ns) / n) / 1000.0

    print(f"JSON-RPC 2.0 Loopback IPC Latency (N={n:,}):")
    print(f"  Round-Trip : p50: {p50:.2f} µs | p95: {p95:.2f} µs | p99: {p99:.2f} µs | mean: {mean:.2f} µs")


if __name__ == "__main__":
    print("================================================================================")
    print(" DELTA INSTITUTIONAL QUANTITATIVE SYSTEM - BENCHMARK REPORT")
    print("================================================================================")
    print(f" Platform : {platform.system()} {platform.release()} ({platform.machine()})")
    print(f" Python   : {platform.python_version()} ({platform.python_implementation()})")
    print(f" CPU Cores: {os.cpu_count()}")
    print("=" * 80 + "\n")

    bench_native_kernels()
    bench_canonical_pipeline()
    bench_ipc_and_bridge()

    print("\n" + "=" * 80)
    print(" BENCHMARK REPORT COMPLETE - ALL FIGURES EMPIRICALLY MEASURED")
    print("================================================================================")
