# DELTA Release Gates — Targets vs Measured

> Authority: code + `docs/STUB_AUDIT.md` + `delta doctor --institutional` + tests.
> Reconciled Date: 2026-10-31 | Current Target: **Release A Only**

## Release Scope Partitioning

DELTA OS explicitly partitions production readiness into two distinct releases:

| Release Phase | Target Scope | Certification Status | Execution Authority |
| :--- | :--- | :---: | :--- |
| **Release A** | Private Research, PIT Factor Lab & Paper Beta | 🟢 **CERTIFIED** (`GO-PAPER`) | Authorized for paper simulation, backtesting, factor research, and terminal TUI/CLI operations. |
| **Release B** | Live Capital Multi-Asset Execution | 🔴 **GATED / HOLD** (`NO-GO-LIVE`) | Strictly fail-closed in-memory (`ERR_LIVE_PROHIBITED`). Blocked until quantitative gates R2–R6, R8–R10 and 14-day live soak pass. |

### Release A Certification Matrix (100% Passed)
- [x] **Native C-ABI Kernel**: Rust SIMD NCM, Black-Scholes, and fast numerical kernels (`tests/test_canonical_end_to_end.py`).
- [x] **PIT Monotonicity**: 4-scenario lookahead bias detector (`tests/test_institutional_readiness_exhaustive.py`).
- [x] **Non-Mutating OMS Journal**: Streaming SHA-256 hash chaining audit with $RPO=0$ (`delta_os/readiness.py`).
- [x] **Paper Broker Sandbox**: Isolated order submission, ack, fill, deduplication, and reconciliation (`execution/paper/broker.py`).
- [x] **Pre-Trade Risk Firewall**: In-memory leverage and fat-finger checks with token-authenticated unlock (`delta_os/safety.py`).
- [x] **Protocol Bridge Security**: 3-tier method permissions (`PUBLIC`, `READ`, `WRITE`) with authenticated `get_state` and stripped query tokens (`delta_os/bridge.py`).
- [x] **Hermetic Packaging**: Full-tree Docker container and cross-platform standalone installers (`Dockerfile`, `scripts/install_standalone.sh`, `scripts/install_standalone.ps1`).

### Release B Quantitative Gating (Pending Live Verification)
- [ ] **R2 (Statistical Edge)**: DSR $\ge 1.8$, t-stat $\ge 2.5$, deflated Sharpe ratio verification across historical walk-forward splits.
- [ ] **R3 (Out-of-Sample)**: Untouched held-out regime evaluation over 2024–2026 market stress windows.
- [ ] **R4 (Stress Testing)**: Macro crisis replay (1987, 2008, 2020, 2023 SVB) with max drawdowns $\le 12\%$.
- [ ] **R5 (Market Capacity)**: Realized fill liquidity and market impact ladder calibration.
- [ ] **R6 (Execution Quality)**: Real-time slippage vs Almgren-Chriss pre-trade bounds.
- [ ] **R8 (Shadow Trading)**: Multi-venue dual-run shadow order stream matching paper allocations.
- [ ] **R9 (Live Candidate)**: Independent penetration test, DAST scanning, and cryptographic secret audit.
- [ ] **R10 (Production Sign-Off)**: Unanimous executive sign-off from all 5 institutional stakeholders.
- [ ] **14-Day Wall-Clock Soak**: Continuous zero-unhandled-exception execution under Sentinel daemon.

---

## The 5 Production Blockers (Reconciled 2026-10-31)
| # | Gap | Status | Resolution & Evidence |
|---|-----|--------|-----------------------|
| 1 | FIX session stub (`execution/sor_venue.py:51`) | 🟢 PAPER CERTIFIED | `execution/fix/initiator.py` + `tests/test_fix_certification.py` (Logon, Heartbeat, Resend, Reject, NOS, ER, Cancel-Replace) |
| 2 | Calendar stub (`data/market_reality.py:173`) | 🟢 IMPLEMENTED | `data/market/exchange_calendar.py` (NYSE/NASDAQ/NSE holidays 2024-27, early closes, DST-safe ET/IST) |
| 3 | Fundamentals placeholder (`data/market/feature_engine.py:230`) | 🟢 IMPLEMENTED | `data/market/fundamentals.py` (EDGAR-cache-first PIT provider, fail-closed) + `ValueFeature` PIT validation |
| 4 | IBKR disabled (`delta_os/brokers.py:153-158`) | 🟢 PAPER CERTIFIED | `execution/adapters/ibkr.py` + `tests/test_ibkr_certification.py` (6/6 tests pass; fail-closed for live capital) |
| 5 | Telemetry format-only (`observability/telemetry.py`) | 🟢 IMPLEMENTED | `observability/exporter.py` (Prometheus scrape endpoint) + `observability/ops_rules.py` (8 canonical SRE rules) |

## Native performance — targets vs measured (from artifacts/bench/bench.json)
| Component | Target | Measured (this box) | Status |
|-----------|--------|---------------------|--------|
| Order book (Native LOB) | 10M ops/s | 212,773 ops/s (N=20,000) | 🟡 MEASURED (FAIL vs 10M target) |
| Matching / Sub-kernels | 10M ops/s | UNAVAILABLE (needs native compile) | 🔴 UNAVAILABLE — do not claim |
| Risk firewall check | 7µs target | p50: 100.8µs, p99: 291.2µs | 🟡 MEASURED (FAIL vs 7µs target) |
| Gateway order submit | 100µs | p50: 24.0µs, p99: 86.5µs | 🟢 MEASURED (PASS) |
| Journal append (fsync) | 1,000µs | p50: 475.9µs, p99: 793.7µs | 🟢 MEASURED (PASS) |

*Benchmark Methodology & Hardware Baseline*: Measurements executed on Linux x86_64 runner (GCC 14/16, Python 3.11/3.13, rustc 1.85+ stable). Workload: N=20,000 synthetic integer-tick orders in FIFO matching queue; Risk firewall: full 12-rule pre-trade invariant check loop with VaR/CVaR and leverage ceilings; Journal: durable SQLite WAL fsync per record. Claim only with: hardware, compiler, flags, dataset, warmup, N, p50/p95/p99/p99.9/max, affinity.

## Finance model (DELTA-FM 0.6B)
Stage: RESEARCH (training works, SFT/QLoRA contract verified, G1–G16 deterministic probes green). NOT production. Live promotion requires untouched held-out GPU benchmarks and independent quant sign-off. Cloud BYOK (Claude 3.7 Sonnet, Gemini 3.8 Flash, DeepSeek v4 Pro) active with deterministic math fallbacks.

## Terminal & CLI Direction (ADR-0006)
- **Rust Ratatui 11-Screen TUI**: Ultra-low latency, institutional calm aesthetic, JetBrains Mono font, micro-header with live status badges.
- **Master Typer CLI**: Full OpenCode 17-command parity suite (`run`, `mini`, `auth`, `models`, `mcp`, `session`, `service`, `plugin`, `stats`, `debug`, `acp`, `api`, `reload`, `pair`, `serve`, `upgrade`, `uninstall`) + 21 institutional quantitative commands.
