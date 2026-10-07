# Runtime verdict: Java / C# / JS (measured 2026-10-07, this box)

Rule: a runtime is used or replaced only on measured proof. No rewrites on belief.

## Measured (this box, outputs read)

- Java gateway unit suites: 4/4 pass (`GatewayTests`: ring FIFO 500, FIX codec,
  matching partial-fill FIFO, cancellation).
- Java loopback STATUS (N=20000, JDK 25.0.1, Win11): **17,711 msgs/s,
  p50 48µs / p95 101µs / p99 148µs** (`benchmarks/java_gateway_bench.json`,
  BENCH_MEASURED). In-memory ring (certified lanes): 14.2M ops/s + 13.3µs p50.
- Python OMS journal (durable, fsync per append): **5,200 ops/s** (this session).
- Pre-trade firewall: ~7µs per check (200-check bench, prior record).

## Verdict

- **Java stays exactly where it is**: execution-plane transport + matching on
  PAPER/SIM rails; live venue adapters remain refusal stubs until R10. It does a
  different job than the Python OMS journal (transport vs durability +
  reconciliation) — replacing the journal with the ring would TRADE AWAY
  crash-recovery for speed. No replacement: not proven, not wanted.
- **C#: not adopted.** No CLR toolchain in this stack; would add a fourth
  runtime, new IPC hops, and untested failure modes for zero measured need —
  JDK25 ring numbers already exceed the transport requirement by 1000x.
- **JS/Node: not adopted.** Frontend is Rust + Python by frozen decision
  (ADR-0006, terminal-only); a JS layer adds IPC latency instead of removing it.
- Trader-visible truth: network/market latency dominates; in-process runtimes are
  not the bottleneck (firewall 7µs, loopback p50 48µs). Ultra-performance comes
  from fewer hops and native kernels (Rust `delta_native`, Java ring), both kept.
