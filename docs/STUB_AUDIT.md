# Stub / Synthetic / Simulation Audit — 2026-09-30 (P0-9), refreshed 2026-10-02 (Phase −1), 2026-10-09 (B8/B9/B10)

Rule (§31): every match is classified SAFE-TEST, RESEARCH-SIM (labeled, never
enters order path), or PRODUCTION-GAP (must be fixed before the capability it
implies may be claimed). Guards verified, not assumed.

## Refresh 2026-10-09 — B8/B9/B10 resolutions (verified, with tests)

Label map to the canonical scale: ✅ CLOSED = Implemented; 🟡 NARROWED / OPEN = Partially validated (residual gap named in Evidence); 🔴 CORRECTED = Not implemented as a capability claim (target unmet, documented with measured evidence). Unknown items stay in the PRODUCTION-GAP table below until measured.

| # | Prior gap / new finding | Status now | Evidence |
|---|---|---|---|
| 5 | Telemetry format-only (row below) | 🟡 NARROWED, still open for prod | `observability/exporter.py` serves real `:9108/metrics` (proven `test_sre_wiring.py::test_exporter_serves_real_delta_series`); canonical `observability/ops_rules.py` + `scripts/sre_check.py` + `docs/SRE_RUNBOOK.md` evaluate real metrics with blindness notes; no prod dashboards/on-call/PagerDuty — stays OPEN for live |
| 6 | Firewall 7µs claim (MEMORY 2026-09-30) | 🔴 CORRECTED: unmet target | Measured 2026-10-09 this box: p50 ~163µs / p99 ~343µs (`artifacts/bench/bench.json`, verdict FAIL vs 7µs plan target); SRE thresholds re-baselined to measured numbers with the gap documented (`ops_rules.py` BASELINE NOTE); the 7µs figure must not be cited until a bench artifact shows it met |
| 7 | `datasets`/`peft` missing from requirements | ✅ CLOSED | Added to `requirements.txt`; `tests/test_ci_security_gates.py::test_requirements_cover_training_imports` pins it; `tests/test_stage2_quantbrain.py` 7/7 green |
| 8 | No CI security gates | ✅ CLOSED (static) | `.github/workflows/security.yml` (semgrep/bandit/secret-scan/cargo-audit/pip-audit, pinned); dynamic DAST/pentest stays OPEN per SECURITY_CERTIFICATION |
| 9 | DR rehearsal unproven | ✅ CLOSED (drill) | `scripts/dr_drill.py` PASS (RPO=0, RTO 0.02s<60s, reconcile RESUME, tamper refused) + `tests/test_dr_drill.py` 4/4; real-SIGKILL + 14-day soak stay OPEN (sign-off matrix) |
| 10 | OMS SUBMITTED had no recovery-cancel edge | ✅ CLOSED | `core/oms/journal.py` SUBMITTED→CANCELLED (crash-window cancel); no prior test weakened (`tests/test_dr_drill.py`) |

Rule (§31): every match is classified SAFE-TEST, RESEARCH-SIM (labeled, never
enters order path), or PRODUCTION-GAP (must be fixed before the capability it
implies may be claimed). Guards verified, not assumed.

## Refresh 2026-10-02 — PRODUCTION-GAP resolutions (verified, with tests)

| # | Prior gap | Status now | Evidence |
|---|---|---|---|
| 1 | FIX stub (`sor_venue.py:51`) | ✅ CLOSED (Python lane) | `execution/fix/initiator.py` full lifecycle + `tests/test_fix_initiator_certification.py`; Java lane paper-only per program |
| 2 | Calendar stub (`market_reality.py:173`) | ✅ CLOSED (NYSE/NASDAQ) | `exchange_calendar.py` wired into `SessionReconstructor`; fallback now counted/visible (`calendar_status`, `fallback_count`) — `tests/test_phase_minus1.py::test_calendar_fallback_is_visible`; CME extension still open |
| 3 | Fundamentals placeholder (`feature_engine.py:230`) | 🟡 OPEN, correctly refused | `ValueFeature.validate` no longer vacuous (P-1.5); missing fundamentals raise with remediation, never NaN |
| 4 | IBKR disabled path (`brokers.py:153-158`) | ✅ CLOSED (adapter, fail-closed) | `delta_os/brokers.py:137-170` delegates to `IBKRClientPortalAdapter`; no-host raises; `tests/test_ibkr_certification.py` 6/6 |
| 5 | Telemetry format-only | 🟡 OPEN as stated | Unchanged; ops telemetry only per ADR-0006 |

Phase −1 additions (2026-10-02): kill-path silent passes fixed (`safety.py`, verified `test_phase_minus1.py` 5 kill tests); PIT zero-lag defaults gated by domain (`construction_pipeline.py`, `timestamps.py`); immortal-universe fixed (`master.py`); purge/embargo defaults 1/1 (`walk_forward/production.py`, `alpha_factory.py`); `reproduce_manifest` verified-not-asserted (`gate.py`); paper ADV unknown marked (`paper/broker.py`); calibrator refuses without data.
Tracked deletions resolved: `tests/unit/test_alpha.py`, `test_pit.py`, `test_statistics.py` are 0-byte placeholders in HEAD — deletion accepted as hygiene, coverage lives in `test_alpha_neutralization.py`, `test_p1_pit_adversarial.py`, `test_quant_research.py`.
Stale in-package test noted (not collected): `data/tick_pit/test_pit.py` imports non-existent `MarketSession` — dead file, do not cite; tracked for later cleanup, outside Phase −1.

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
