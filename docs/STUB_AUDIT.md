# Stub / Synthetic / Simulation Audit — 2026-09-30 (P0-9)

Rule (§31): every match is classified SAFE-TEST, RESEARCH-SIM (labeled, never
enters order path), or PRODUCTION-GAP (must be fixed before the capability it
implies may be claimed). Guards verified, not assumed.

## PRODUCTION-GAP (do not claim the capability)

| # | Location | Finding | Required before claim |
|---|---|---|---|
| 1 | `execution/sor_venue.py:51` | FIX 4.4 session is an explicit **stub** (seq nums + gap detect + cert checklist only) | Full FIX (§13): Logon/Heartbeat/TestRequest/Logout, ResendRequest, Reject, NewOrderSingle, ExecutionReport, Cancel/Replace, recovery, reconnect, persistence + certification tests |
| 2 | `data/market_reality.py:173` | Exchange sessions are a **calendar stub** (fixed hours) | Real calendar layer: holidays, early closes, DST, halts, auctions (§14) |
| 3 | `data/market/feature_engine.py:230` | Fundamental-data fetch is a **placeholder** | Real fundamentals feed or remove fundamental features from claims (§15) |
| 4 | IBKR path `delta_os/brokers.py:153-158` | Explicit disabled path (`raise BrokerError`) | Venue adapter + certification; until then IBKR is NOT IMPLEMENTED |
| 5 | `observability/telemetry.py:3` | In-memory counters/histograms + Prom exposition **format only** (p50/p99 computed, no external exporter) | Scrape/push exporter + instrumentation coverage per span (§28); values recorded are real where instrumented |

## RESEARCH-SIM (labeled, guarded — keep, do not promote)

| Location | Guard verified |
|---|---|
| `delta_os/data_router.py` TIER3-SYNTH + `[STALE DATA]` badges | `safety.py:128-131` refuses orders on stale/synth; `repl.py:441-442` refuses backtest on synth |
| `data/router.py` synthetic (`synthetic_enabled=False` default) | Opt-in only; `risk/pre_trade/validation.py:47` + `firewall.py:180` reject `synthetic/demo_fallback/hash_seeded` price sources |
| `research/agent/research_loop.py` synthetic-score fallback | Labeled per-iteration `tool_used`; `strict=True` propagates instead; `synthetic_used` aggregate added 2026-09-30 |
| `simulation/*`, replay, digital twin | Deterministic sims; must consume real event data before microstructure claims (§11) |

## SAFE-TEST (keep)

`trading/kill_switch.py:142` historical placeholder note (now wired); `data/tick_pit/pit_store.py:279-280` SQL placeholders (parameter binding, correct); `delta_os/llm_gateway.py` greeting fallback (labeled, non-numerical); `delta_os/brokers.py:11` honest-stub comment (refuses rather than fills).

## Counts (production-path roots only)

synthetic 73 (majority: guards + sim labels), stub 5, placeholder 10, fake 2 (both are refusal rules, not fabrication).
