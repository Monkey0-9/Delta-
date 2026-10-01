# DELTA Release Gates — targets vs measured (P0 blocker)

> Authority: code + `docs/STUB_AUDIT.md` + tests. Old status percentages are NOT truth.

## Rule
A capability may be claimed **only** when: canonical implementation + tests + failure handling + telemetry + deterministic behavior + owner. `all()` gates must pass; mean() is forbidden.

## The 5 production blockers (from STUB_AUDIT 2026-09-30)
| # | Gap | Status | Unblocks when |
|---|-----|--------|---------------|
| 1 | FIX session stub (`execution/sor_venue.py:51`) | 🔴 NOT IMPLEMENTED | Logon/Heartbeat/TestRequest/Logout/Resend/Reject/NOS/ER/Cancel-Replace/recovery/reconnect/persistence + cert tests |
| 2 | Calendar stub (`data/market_reality.py:173`) | 🟡 FIXED 2026-10-01 — `data/market/exchange_calendar.py` (NYSE/NASDAQ holidays 2024-27, early closes, DST-safe ET) wired into `SessionReconstructor(label, is_open)` | ✅ done — needs CME extension for futures |
| 3 | Fundamentals placeholder (`data/market/feature_engine.py:230`) | 🟡 FIXED 2026-10-01 — `data/market/fundamentals.py` (EDGAR-cache-first PIT provider, fail-closed) + `ValueFeature` refuses without PIT fundamentals | ✅ done — needs live EDGAR backfill for coverage |
| 4 | IBKR disabled (`delta_os/brokers.py:153-158`) | 🔴 NOT IMPLEMENTED | Venue adapter + certification; do not claim |
| 5 | Telemetry format-only (`observability/telemetry.py`) | 🟡 FIXED 2026-10-01 — `observability/exporter.py` (Prom scrape endpoint, no deps) | ✅ done — needs Grafana/alerts wiring |

## Native performance — targets vs measured
| Component | Target | Measured | Status |
|-----------|--------|----------|--------|
| Order book | 10M ops/s | NOT MEASURED (needs compile) | 🔴 do not claim |
| Matching | 10M ops/s | NOT MEASURED | 🔴 do not claim |
| Event queue (Rust) | 5M ops/s | NOT MEASURED | 🔴 do not claim |
| Data ingest | 10M ticks/s | NOT MEASURED | 🔴 do not claim |
| Risk firewall | 7µs | 7µs (200-check bench, local) | 🟡 micro-bench only, e2e unmeasured |

Claim only with: hardware, compiler, flags, dataset, warmup, N, p50/p95/p99/p99.9/max, affinity.

## Finance model (Soup 0.6B)
Stage: RESEARCH (training works, SFT works). NOT production. G1–G16: 5 rule probes green, 11 now have deterministic smoke probes (2026-10-01), full benchmark/calibration/shadow still required before promotion.

## TUI direction (frontend-design skill)
Aesthetic: **institutional calm** — near-black `#080909`, teal `#20C9A6` data-first, JetBrains Mono. Anchor: micro-header `▲ DELTA | QUANT INTELLIGENCE CLI | ● MARKETS ● DATA ● RISK ⬡ MODE | clock` + hero RESEARCH/SIMULATE/ANALYZE/EXECUTE/LEARN. Density without fatigue; keyboard-first; no futuristic chrome.
