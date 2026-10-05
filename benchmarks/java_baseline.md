# DELTA Benchmark Honesty & Measurement Baseline

**Standard**: No aspirational numbers. All latency and throughput metrics must be measured on documented hardware with warm-up cycles, sample sizes $N \ge 1,000,000$, and complete percentile distributions. Unmeasured claims must be marked `UNMEASURED`.

---

## 1. Benchmark Execution Environment
- **CPU**: AMD Ryzen / Intel Core (Exact model recorded per run)
- **RAM**: Physical RAM capacity & frequency
- **OS**: Windows 11 Pro / Server (Build 26200)
- **JDK**: OpenJDK 25.0.1 LTS
- **JVM Flags**: `-Xms2g -Xmx2g -XX:+UseZGC` or `-XX:+UseParallelGC`
- **Power Plan**: High Performance

---

## 2. Standard Benchmark Reporting Schema

| Metric | Target / SLA | Measured Value | Provenance |
| :--- | :--- | :--- | :--- |
| **SPSC Ring Throughput** | $\ge 5,000,000$ ops/sec | Measured in Group 02 | `BENCH_MEASURED` |
| **SPSC Ring Latency p50** | $< 100$ ns | Measured in Group 02 | `BENCH_MEASURED` |
| **SPSC Ring Latency p95** | $< 250$ ns | Measured in Group 02 | `BENCH_MEASURED` |
| **SPSC Ring Latency p99** | $< 500$ ns | Measured in Group 02 | `BENCH_MEASURED` |
| **Loopback TCP Bridge Tax**| $< 40$ µs | Measured in Group 02 | `BENCH_MEASURED` |
| **FIX 4.2 Decode / Encode** | $\ge 1,000,000$ msg/sec | Measured in Group 05 | `BENCH_MEASURED` |
| **Order Book Match Latency**| $< 2$ µs | Measured in Group 09 | `BENCH_MEASURED` |
