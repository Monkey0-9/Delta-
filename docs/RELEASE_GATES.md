# DELTA Release Gates — targets vs measured (P0 blocker)

> Authority: code + `docs/STUB_AUDIT.md` + tests. Old status percentages are NOT truth.

## Rule
A capability may be claimed **only** when: canonical implementation + tests + failure handling + telemetry + deterministic behavior + owner. `all()` gates must pass; mean() is forbidden.

## The 5 production blockers (from STUB_AUDIT 2026-09-30 — Reconciled 2026-10-23)
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
