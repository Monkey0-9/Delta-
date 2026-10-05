# ADR 0007: DELTA Java Execution Plane & Disruptor Architecture

## Status
Accepted

## Context
DELTA requires institutional-grade execution capabilities, specifically:
1. Low-latency, lock-free order routing and price-time FIFO matching.
2. High-throughput FIX 4.2 / 4.4 framing, execution reports, and drop-copy stream processing.
3. Strict mechanical sympathy: zero-allocation in hot paths, off-heap cache-line alignment, and deterministic microsecond latencies.

While Rust remains the authoritative driver for the Ratatui TUI and core native numerical kernels, and Python remains the authoritative driver for quant research, alpha models, regime classification, and AI/agent orchestration, a dedicated low-garbage Java execution engine (utilizing the LMAX Disruptor pattern) provides a verified enterprise-grade execution lane.

## Decisions

1. **Pure-JDK 25 Baseline**: Zero external jar dependencies (no Maven/Gradle required, standard `javac` compilation targeting `--release 25`). Avoids dependency bloat and vulnerability vectors (SBOM of zero).
2. **Default-Off / Paper-Only**: The Java execution plane is default-off and strictly restricted to `PAPER` and `SIM` execution environments. Live routing is rejected at the architecture level until all Group 29 promotion gates pass.
3. **No-Fork Invariant**: The Java execution plane must never maintain a split ledger, invent prices, or bypass the canonical 12-stage quantitative pipeline and pre-trade risk firewall. All fills must flow into the Python OMS and ledger for three-way reconciliation.
4. **Audit Hash-Chain Subordination**: Every Java record must compute SHA-256 over its canonical payload and cross-link to the parent Python audit hash chain.
5. **Fail-Closed Supervision**: If the Java execution process crashes, terminates, or hangs, the TUI and Python runtime must remain healthy, flagging the lane as `DEGRADED` or `JAVA_UNAVAILABLE`, with zero impact on risk containment.
6. **Benchmark Honesty**: All performance claims must specify exact hardware, OS, JDK flags, sample size $N \ge 1,000,000$, and report $p50$, $p95$, $p99$, and max latencies. Unmeasured claims must be marked `UNMEASURED`.

## Non-Goals
- **No UI in Java**: Terminal interface remains strictly in Rust Ratatui.
- **No Strategy Logic in Java**: Quantitative strategy signals, regime inference, and alphas remain strictly in Python / Rust.
- **No Risk Authority in Java**: Pre-trade limits and the primary emergency kill switch remain authoritative in the Python Risk Firewall and Rust native circuit breaker. Java is strictly an execution worker.

## Consequences
- Clean separation of concerns: Rust for terminal, Python for quant intelligence, Java for lock-free OMS matching and FIX protocol framing.
- Reproducible, zero-dependency build on any box with JDK 25 LTS installed.
