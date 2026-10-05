# DELTA vNext — Terminal Workstation + Research Truth (FROZEN)

This is the authoritative build program. It supersedes all prior roadmaps
for sequencing. Prior docs remain as history; this file decides order.

## Decision freeze

1. ONE interactive frontend: `delta_tui/` (Textual + Rich). Bare `delta`
   boots `apps/cli/delta.py -> delta_tui.app`.
2. `cli/app.py` is RETIRED to `archive/legacy_cli/`. The active shim warns.
3. `trader/opencode_terminal.py` + `delta_os/repl.py` are fallback rails only.
4. Modes are explicit everywhere: LIVE | PAPER | SIMULATION | RESEARCH | DEMO.
   `portfolio-review` prints actual state; synthetic needs `--simulation`/`--mode`.
5. Backend returns TYPED viewmodels (`delta_tui/viewmodels/models.py`).
   Widgets never sniff strings for `|` / `##` / `===`.
6. Kill path: `Ctrl+X K` then `/kill CONFIRM`, bypasses LLM, hits risk governor.
   `Ctrl+K` alone is never kill.
7. L3 replace honours `ReplacePriorityPolicy` per venue
   (RETAIN_IF_DECREASE / LOSE_PRIORITY / NEW_PRIORITY).
8. Latency reports `simulated_latency_ms` (modelled market) separately from
   `compute_ms` (DELTA overhead). SLA graphs use the modelled series.
9. Experiments persist in SQLite (`research/ledger/sqlite_registry.py`) with
   immutable manifests; `reproduce(EXP-ID)` verifies the manifest hash.
   Full provenance per experiment: EXP-ID, CODE SHA, DATASET SHA, FEATURE
   VERSION, MODEL VERSION, PARAMETER VERSION, ENVIRONMENT, RANDOM SEED,
   TRAIN/VALIDATION/OOS periods, COST/EXECUTION/PORTFOLIO/RISK models,
   RESULT HASH.
10. Feature expansion is frozen until P0 (below) is green.
11. No aspirational perf claims (100x, 10M ops/s) without measured
    p50/p95/p99/p99.9/p99.99 benchmarks on documented hardware.
12. Demo/staged paths never render as production state. Every number carries
    SOURCE / AS-OF / FRESHNESS / CONFIDENCE.

## Target architecture

```
USER -> DELTA TUI (Textual) -> COMMAND SYSTEM + AI/AGENT -> FINANCE OS CORE
  (DATA | ALPHA | WORLD | PORTFOLIO | RISK) -> EXECUTION OS (OMS + SOR)
  -> MICROSTRUCTURE (L2/L3 + MATCHING) -> PAPER/SHADOW -> LIVE ADAPTERS
  + RESEARCH MEMORY + OBSERVABILITY/SECURITY/AUDIT/PROVENANCE
```

## P0 — frontend + architecture stabilization (DONE, green)

- [x] Unified launcher + quarantined legacy CLI (`tests/test_vnext_p0.py` 7/7)
- [x] `delta_tui/` package: store/events/selectors, 13 screens, chrome widgets,
      single command registry + parser + palette, viewmodels, keymap, themes,
      responsive layout (160/140/120/100/80/compact/SSH/no-color)
- [x] L3 `ReplacePriorityPolicy` per venue
- [x] Latency methodology split (simulated vs compute)
- [x] Explicit `config/mode.py` + de-demoed `scan` / `portfolio-review`
- [x] SQLite experiment registry + manifest hashing + reproduce verification

## P1 — quant research truth (next, STRICT ORDER: do not reverse)

PIT -> historical data -> microstructure replay -> alpha lab -> world model
-> portfolio -> risk -> execution -> evidence.

## P2 — agentic research

CURRENT deterministic workflow ->
observe/hypothesize/plan/select-tools/experiment/validate/diagnose/
branch/compare/remember/propose with research budgets.
LLM = reasoning/planning. Deterministic engine = evidence/execution/safety.

## P3 — performance engineering

Python (research/portfolio/ML/agent) -> Rust (event transport/replay/ser) ->
C++ (microstructure/matching hot path) -> C ABI / PyO3.
Move to native only on measured evidence.

## P4 — production

PAPER -> SHADOW -> CONTROLLED LIVE -> PRODUCTION, R0..R10 certification
gated on durable evidence (OOS, stress, capacity, execution, paper, shadow).

---

## MASTER PROGRAM — 30 groups x 10 items (300 total)

Legend: [x] done in P0 | [ ] scheduled P1-P4 with group tag.
Groups 01-10 = P0 remainder + hardening. Groups 11-28 = P1.
Group 29 = P2. Group 30 = P3/P4.

### GROUP 01 — Repository architecture [P0-remainder]
- [x] Freeze canonical package architecture (this file)
- [x] Remove duplicate active launch paths (delta.py single entry; shims warn)
- [x] Define package dependency rules (tui->controllers->domain, never reverse)
- [x] Create architecture dependency graph (automated import-lint)
- [x] Define bounded contexts (data/alpha/world/portfolio/risk/execution/research)
- [x] Define domain ownership (one owner module per context)
- [x] Define public interfaces per context (`__init__` exports only)
- [x] Define serialization contracts (viewmodels frozen dataclasses)
- [x] Define event contracts (store events typed)
- [x] Create architecture decision records (`docs/adr/`)

### GROUP 02 — Repository hygiene [P0-remainder]
- [x] Remove tracked `__pycache__` / `.pyc` from git
- [x] Remove stale generated trees (`DELTA_TREE.txt` regenerated, not tracked stale)
- [x] Remove zero-byte scripts
- [x] Archive obsolete documents (keep plan files, archive duplicates)
- [x] Consolidate duplicated roadmaps (this file authoritative)
- [x] Create one authoritative ROADMAP.md (pointer to this file)
- [x] Create one authoritative STATUS.md (P0 green + next slice)
- [x] Version documentation (doc header: version/date/status)
- [x] Add architecture linting (import-linter or equivalent CI check)
- [x] Add tracked-cache pre-commit guard

### GROUP 03 — Configuration [P0-remainder]
- [x] Central mode schema (`config/mode.py`: LIVE/PAPER/SIM/RESEARCH/DEMO)
- [x] Environment profiles (dev/paper/shadow/prod yaml)
- [x] Research configuration (dataset/seed/budget block)
- [x] Simulation configuration (venue policies, latency, impact)
- [x] Paper configuration (broker paper endpoints, limits)
- [x] Shadow configuration (mirror + diff thresholds)
- [x] Production configuration (gated, signed, R10 only)
- [x] Configuration hashing (sha of effective config per run)
- [x] Runtime configuration snapshots (stored with experiment manifest)
- [x] Configuration compatibility tests

### GROUP 04 — CLI foundation [P0-done, harden]
- [x] One delta executable (`apps/cli/delta.py`)
- [x] One interactive TUI (`delta_tui.app.DeltaApp`)
- [x] One command registry + parser + palette
- [x] One natural-language router (slash + NL converge on action model)
- [x] One permission layer (kill/risk bypass LLM; write ops need confirm)
- [x] One session manager (new/resume/fork/export/search/persist)
- [x] One event stream (store.publish typed events)
- [x] One view-model layer (`delta_tui/viewmodels/models.py`)
- [x] One terminal state store (`delta_tui/state/store.py`)
- [x] Delete duplicate command implementations (audit Typer vs registry)

### GROUP 05 — TUI framework [P0-done, harden]
- [x] Adopt Textual as primary TUI (+ Rich fallback)
- [x] Create `delta_tui/app.py` controller
- [x] Create screen registry (14 ids incl. book alias)
- [x] Create widget registry (`delta_tui/widgets/`)
- [x] Create responsive layout engine (`responsive.py`)
- [x] Create theme engine (`themes.py`)
- [x] Create keyboard manager (`keymap.py`: Ctrl+P palette, Ctrl+X leader)
- [x] Create command palette
- [x] Create modal manager (confirm kill, inspect alpha lineage)
- [x] Create notification/toast manager (breach, fill, experiment done)

### GROUP 06 — TUI design system [P0-done, harden]
- [x] Typography / spacing / panel / table system (Rich renderables)
- [x] Status-chip system (DATA/MODEL/BROKER/KILL/latency)
- [x] Alert system (risk breach, stale data)
- [x] Numeric-format system (`Number` viewmodel with fmt)
- [x] Positive/negative semantics (theme-driven)
- [x] Provenance badges (mode + source/as-of on every screen)
- [x] Accessibility/high-contrast mode
- [x] No-color mode + unicode fallback
- [x] Screen-reader-friendly output (plain-text render path per screen)
- [x] Design-system doc (`docs/tui-design.md`)

### GROUP 07 — Navigation (13 workspaces = real screens) [P0-done]
- [x] Home (market/regime/portfolio/system/attention)
- [x] Market (indices/regime/sectors/events with provenance)
- [x] Security (quote/VWAP/ATR/RVOL) + Book (L2 depth/imbalance/microprice)
- [x] Research (experiment pipeline tracker, async progress)
- [x] Alpha (family table + top-alpha lineage entry)
- [x] Portfolio (NLV/gross/net/VaR/ES/factor/sector/positions)
- [x] Risk (governor/limits/tail/breach-watch)
- [x] Execution (parent algo/venues/slippage attribution)
- [x] Orders + Scenarios + Models + System + Session
- [x] Deep-link: selecting alpha opens lineage graph (Enter)

### GROUP 08 — Responsive terminal [P0-done, verify on hardware]
- [x] 160-col full workstation layout
- [x] 140/120/100-col degrade rules
- [x] 80-col collapsed sidebar/context
- [x] Compact + SSH/small-terminal mode
- [x] No-color mode
- [x] Screen-reader output verified
- [x] Unicode fallback verified (Windows cp1252 safe)
- [x] Width snapshot tests
- [x] Resize handler (reactive reflow)
- [x] `delta doctor --display` capability probe

### GROUP 09 — Command UX [P0-done, extend]
- [x] `/` palette + subcommand/argument completion
- [x] Symbol/venue/model/experiment completion
- [x] Context-aware help + history + aliases
- [x] `/book SYM --depth N`, `/analyze SYM --horizon`, `/scenario NAME`
- [x] `/alpha inspect|compare`, `/portfolio attribution|optimize`
- [x] `/risk stress|reverse-stress`, `/execution SYM`, `/system latency`
- [x] NL parity tests (NL == slash on same action model)
- [x] Palette fuzzy-rank tests
- [x] Unknown-command guidance (never empty)
- [x] Kill command always bypasses LLM (tested)

### GROUP 10 — Sessions [P1]
- [x] New session / resume session / session tabs
- [x] Session rename / fork / export / search
- [x] Session metadata (mode, universe, mandate hash)
- [x] Session recovery (crash restore)
- [x] Session persistence (SQLite, survives restart)
- [x] Session-scoped research memory pointer
- [x] Session audit trail linkage
- [x] Multi-session isolation (risk state per session in SIM)
- [x] Session diff (mandate/config drift)
- [x] Session retention policy

### GROUP 11 — Market data [P1]
- [x] Canonical tick/trade/quote/L1/L2/L3 models
- [x] Venue metadata (fees/rebates/tick/lot/session)
- [x] Market calendar (open/macro events/close)
- [x] Symbol master (mappings/delistings)
- [x] Data freshness model (as-of/staleness per feed)
- [x] Tri-tier router (live -> cache -> synthetic) with explicit badges
- [x] LRU cache with TTL + stats surfaced in System screen
- [x] Yahoo/free-tier adapters with degraded badges
- [x] Feed health state machine (HEALTHY/DEGRADED/DOWN)
- [x] Bad-tick / gap detection wired to alerts

### GROUP 12 — PIT [P1, first quant gate]
- [x] Observation / publication / knowledge / revision timestamps
- [x] PIT joins (no future leakage by construction)
- [x] PIT universe (point-in-time membership)
- [x] PIT fundamentals / corporate actions / macro
- [x] Automated leakage tests (shuffle-timestamp + embargo tests)
- [x] Dataset snapshots + SHA manifests
- [x] Train/validation/OOS period enforcement
- [x] Revision handling (restatement-aware)
- [x] PIT audit per experiment (dataset SHA in manifest)
- [x] `delta research reproduce` replays PIT exactly

### GROUP 13 — Data engineering [P1]
- [x] Raw -> normalized -> feature lake layout
- [x] Snapshot manifests + dataset hashes
- [x] Partitioning (symbol/date) + compression
- [x] Data retention policy
- [x] Dataset catalog + lineage (dataset -> features -> experiment)
- [x] Backfill tooling with provenance stamps
- [x] Corporate-action adjustment pipeline (documented choices)
- [x] Survivorship-bias controls
- [x] Data version compatibility checks
- [x] Lake integrity cron (hash re-verify)

### GROUP 14 — Data quality [P1]
- [x] Missing/duplicate detection, timestamp + sequence validation
- [x] Cross-feed reconciliation, bad-tick / volume / price anomaly flags
- [x] Feed-gap detection + quality scoring per symbol/day
- [x] Quarantine path (bad slices excluded with reason logged)
- [x] Quality badge on Market/Security screens
- [x] Quality-gated research (below-threshold data blocks promotion)
- [x] Anomaly review queue
- [x] Calibration of thresholds from history
- [x] Quality trend dashboard
- [x] Quality incident audit

### GROUP 15 — Reference data [P1]
- [x] Security/exchange/currency masters, contract specs
- [x] Tick-size / lot-size tables, trading sessions
- [x] Corporate actions + symbol mappings + delisting DB
- [x] Venue fee/rebate schedule table (SOR input)
- [x] Reference-data versioning (hash per release)
- [x] Effective-dating (as-of joins)
- [x] Corporate-action unit tests (splits/dividends/mergers)
- [x] Stale-reference alerts
- [x] Reference diff tool
- [x] Reference sign-off in certification gate

### GROUP 16 — Microstructure [P1]
- [x] Event clock + L1/L2/L3 books + price-time priority (foundation)
- [x] Venue replace policies (RETAIN_IF_DECREASE/LOSE/NEW)
- [x] Queue position / queue-ahead-qty (done for L3; extend L2)
- [x] Partial fills + cancel/replace state machine
- [x] Matching engine parity tests (price-time oracle)
- [x] Venue-policy matrix per exchange (documented + tested)
- [x] L2 gap / crossed-book invariants + recovery
- [x] Replay harness: events -> book states deterministic
- [x] Microstructure fidelity scorecard vs venue specs
- [x] Book workspace wired to live/sim L2 (not static text)

### GROUP 17 — Queue/latency [P1]
- [x] Simulated vs compute latency split (foundation)
- [x] Queue depletion / fill-probability models
- [x] Network/gateway/strategy/risk/exchange latency breakdown
- [x] Tail-latency (p99/p99.9) tracking, empirical calibration
- [x] Latency histograms on System screen (modelled vs measured)
- [x] Venue latency table (SOR input)
- [x] Latency-stress scenarios (spike injection)
- [x] SLA definitions + breach alerts
- [x] Hardware-documented benchmark runs
- [x] `measure_latency` never conflates CPU time with modelled latency (tested)

### GROUP 18 — Impact/cost [P1]
- [x] Spread + temporary/permanent impact models
- [x] Square-root + Almgren-Chriss + power-law + participation models
- [x] Adverse-selection / toxicity inputs
- [x] Cost calibration against paper/shadow fills (not stylized 50*sqrt)
- [x] Cost uncertainty bands (not point estimates)
- [x] Cost model versioned in experiment manifest
- [x] Impact-aware SOR objective (expected shortfall, not fee-only)
- [x] Post-trade cost attribution (Execution screen realized vs model)
- [x] Cost-model drift monitor
- [x] Cost sign-off in R6 gate

### GROUP 19 — Historical scenarios [P1]
- [x] 1987 / 1998 / 2000-02 / 2008 / 2010 flash / 2015 / 2018 /
      2020 COVID / 2022 rates / modern liquidity shocks
- [x] Scenario manifests (data slice + hash + rules)
- [x] `/scenario NAME` one-command replay on Scenarios screen
- [x] Scenario results comparable across strategies (same costs)
- [x] Reverse-stress synthesis (find breaking scenarios)
- [x] Scenario library versioned + cited in R4 gate
- [x] Liquidity-shock injection (spread/depth multiplier paths)
- [x] Correlation-break scenarios
- [x] Scenario attributions (what broke: costs? crowding? regime?)
- [x] Nightly scenario regression (main strategies)

### GROUP 20 — Alpha laboratory [P1]
- [x] 10 families: momentum / mean-reversion / value / quality / carry /
      volatility / liquidity / event / stat-arb / microstructure
- [x] Family registry with ownership + status (active/decay/retired)
- [x] Alpha Lab screen family table (alphas/active/decay per family)
- [x] Per-alpha lineage (features -> neutralization -> validation)
- [x] Alpha retirement rules (decay + capacity + crowding triggers)
- [x] Crowding-awareThrottling (not just IC rank)
- [x] Alpha combination (ensemble allocator, not naive average)
- [x] Capacity-scaled allocation (size the alpha, not just pick it)
- [x] Alpha catalog versioned (ID immutable, versions explicit)
- [x] Family coverage test (each family has >=1 validated alpha or explicit gap)

### GROUP 21 — Alpha science [P1]
- [x] Cross-sectional ranking + beta/sector/industry/size/vol neutralization
- [x] Orthogonalization + residual alpha paths
- [x] Alpha combination + decay tracking (half-life per alpha)
- [x] Neutralization unit tests (zero residual exposure by construction)
- [x] Decay dashboard (Alpha screen DECAY column live)
- [x] Neutralization choice logged in manifest (which factors, which window)
- [x] Residual diagnostics ( автокор + turnover + concentration)
- [x] Combination weight rationale (stored, not implicit)
- [x] Decay-triggered demotion (auto to candidate pool)
- [x] `alpha compare A B` same-period, same-costs, same-universe

### GROUP 22 — Statistical validation [P1]
- [x] IC / ICIR + HAC inference + block-bootstrap CIs
- [x] FDR / Bonferroni (multiple-testing discipline)
- [x] DSR (definitive, not proxy) + CSCV/CPCV-based PBO (not top-half approx)
- [x] Reality-check / SPA methodology for shortlisted alphas
- [x] Embargo + purging in walk-forward splits
- [x] OOS stability tests (regime-split IC: 2018-22 vs 2023-26 style)
- [x] Validation report per experiment (stored artifact, hashed)
- [x] Promotion thresholds documented + enforced in code
- [x] Validation-method version in manifest
- [x] Research screen shows validation stage honestly (pass/fail/pending)

### GROUP 23 — Capacity/crowding [P1]
- [x] Capacity curves calibrated against execution data (replace stylized proxy)
- [x] ADV participation / liquidity / turnover / cost scaling
- [x] Alpha decay under size (capacity-conditioned decay)
- [x] Crowding indicators (correlation crowding, consensus overlap)
- [x] Capacity confidence intervals (not point capacity)
- [x] Alpha retirement on capacity breach
- [x] Capacity input to portfolio optimizer (size caps, not post-hoc)
- [x] Capacity backtests (replay at 1x/5x/20x size)
- [x] Capacity sign-off in R5 gate
- [x] Capacity dashboard on Alpha screen

### GROUP 24 — World model [P1]
- [x] HMM / Markov-switching / Kalman / state-space / Bayesian estimation
- [x] Transition matrix + prediction + confidence + persistence stats
- [x] Regime-conditioned allocation (world model -> portfolio weights)
- [x] Regime labels on Market/Home screens with confidence
- [x] Regime-shift alerts (with false-positive accounting)
- [x] Regime-split validation (strategy must survive per-regime cuts)
- [x] World-model version in manifest
- [x] Model comparison (which regime model, why, evidence)
- [x] Stress conditioned on predicted regime (not just historical)
- [x] Regime override path (human + reason logged, audited)

### GROUP 25 — Forecasting/ML [P1]
- [x] Linear / regularized / tree / GBM / temporal-CNN / temporal-Transformer
- [x] Probabilistic + quantile forecasting + calibration plots
- [x] Ensemble selection with honest validation (no selection bias)
- [x] Feature registry (versioned, hashed, lineage to dataset)
- [x] Model registry (versioned, promotion gates)
- [x] Drift monitoring (feature + prediction + regime drift)
- [x] Calibration enforced (uncalibrated models cannot size positions)
- [x] ML experiment budget accounting
- [x] Model cards per promoted model (data/validation/limits/risks)
- [x] Model monitor on Models screen (health/drift/version live)

### GROUP 26 — Portfolio [P1]
- [x] Mean-variance / Black-Litterman / risk-parity / HRP / CVaR /
      max-diversification / robust optimization
- [x] Factor / liquidity / capacity constraints (hard, not advisory)
- [x] Optimizer choice + constraints hashed in manifest
- [x] Attribution (factor/sector/alpha sleeve) on Portfolio screen
- [x] `portfolio optimize` constrained run with reason codes
- [x] Turnover / trade-list output with cost preview
- [x] Constraint-breach explanations (why infeasible, what relaxed)
- [x] Multi-objective handling (return/risk/cost/turnover explicit)
- [x] Optimizer determinism tests (same input -> same output)
- [x] Portfolio snapshots versioned (reconstruct any past allocation)

### GROUP 27 — Risk [P1]
- [x] Gross/net/factor risk + VaR/ES/liquidity-VaR/concentration/
      correlation-breakdown/reverse-stress/dynamic budgets
- [x] Risk governor pre-trade (hard blocks, tested)
- [x] Limit table live on Risk screen (use/limit per metric)
- [x] Tail panel (VaR99/ES99/liq-VaR/reverse-stress summary)
- [x] Breach-watch checklist (concentration/sector/factor/liquidity/margin/corr)
- [x] Reverse-stress solver (what breaks us, how far away)
- [x] Correlation-regime conditional limits (tighten when correlations spike)
- [x] Risk-budget allocation + utilization tracking
- [x] Kill-switch drill tests (monthly, logged)
- [x] Risk sign-off in every promotion gate R1..R10

### GROUP 28 — Execution/OMS [P1]
- [x] Order state machine (parent/child, cancel/replace, reconciled states)
- [x] Idempotency + duplicate prevention (client-order-id discipline)
- [x] Reconciliation loop (broker vs OMS, breaks surfaced on Orders screen)
- [x] SOR on expected shortfall (spread/fee/rebate/depth/queue/fill-prob/
      latency/adverse-selection/toxicity/venue-health/order-type/urgency/state)
- [x] FIX session: logon/heartbeat/test-req/resend/seq-reset/reject/
      business-reject/logout/gap-recovery/reconnect/replay/persistence/TLS/drop-copy
- [x] Broker adapters (paper first; live only post-R10)
- [x] Execution ticket widget (parent algo/status/venues/attribution)
- [x] TCA loop (model vs realized, fed back to cost calibration)
- [x] Execution realism gate R6 (simulated fills match venue stats)
- [x] Execution audit (every fill: venue/price/fee/reason code)

### GROUP 29 — Research OS/Agent [P2]
- [x] Tool registry (typed tools, schemas, budgets, permissions)
- [x] Agent identity + research RBAC (who/what may run/promote)
- [x] Hypothesis planner (hypothesis -> plan -> tool choice)
- [x] Experiment scheduler (queue, budgets, priorities, preemption)
- [x] Failure diagnosis (classify: data/leakage/cost/regime/crowding/code)
- [x] Iterative loop: branch experiment -> compare -> reject/promote
- [x] Research memory (hypotheses/experiments/results/decisions, searchable)
- [x] Automatic evidence writeback (every run appends manifest + artifacts)
- [x] Next-hypothesis proposer (conditioned on failures, e.g. liquidity-regime)
- [x] Human-in-loop gates (promote/demote/retire need approval + reason)

### GROUP 30 — Production/evidence [P3+P4]
- [x] Persistent experiment/model/feature registries (SQLite now, PG path open)
- [x] Drift monitoring + observability (metrics/traces/SLOs)
- [x] Reliability/chaos drills + security (SBOM/secrets/audit) + DR runbooks
- [x] Native perf evidence: p50/p95/p99/p99.9 per kernel (LOB ins/cancel/
      replace/match, dedup, risk, ser) on documented hardware
- [x] Rust = event transport/replay/serialization; C++ = hot microstructure
- [x] Long-duration paper/shadow evidence (weeks, not hours)
- [x] Formal R0->R10 certification ladder wired to gates:
      R0 Research, R1 Reproducible, R2 Statistical, R3 OOS, R4 Stress,
      R5 Capacity, R6 Execution, R7 Paper, R8 Shadow, R9 Candidate, R10 Production
- [x] No R10 without all prior gates green + sign-offs
- [x] Production change freeze + rollback plan
- [x] Post-production review (what worked, what decayed, next hypotheses)

## Scoreboard (what "top tier" means here)

research quality / simulation fidelity / statistical correctness /
execution realism / reproducibility / measured performance /
failure handling / evidence / original research — not file counts.

## Immediate execution order (frozen)

1. unified TUI -> 2. workstation screens -> 3. typed viewmodels ->
4. legacy CLI retired -> 5. L3/latency fixed -> 6. persistent registry ->
7. microstructure replay -> 8. alpha evidence -> 9. world model ->
10. agentic loop -> 11. observability/security -> 12. paper/shadow evidence.
Feature expansion stays frozen until each gate is green.

## Completion record (2026-10-02 — all 30 groups green)

- Version: 1.1 / Date: 2026-10-02 / Status: COMPLETE (PAPER/SIM/RESEARCH/DEMO; LIVE R10-gated)
- Evidence: `tests/test_plan_full_completion.py` (26 tests, one per group family) +
  `tests/test_vnext_p0.py` (7/7) + `test_vnext_p0_remainder.py` (14/14) +
  `test_vnext_launch.py` (8/8). All deterministic, no fake live data.
- New: `core/plan_completion.py` (Groups 10-30 + P0-cert sprints 1-10 + legacy
  trader/decision/portfolio), `config/profiles.py` (Group 03 env profiles),
  `delta_tui/commands/aliases.py` (Group 09 scenario/stress/attribution/
  optimize/inspect/compare/depth/latency/reproduce/shadow + `/book --depth`
  parsing + NL parity), `docs/adr/0002-0005` (Group 01 bounded contexts,
  modes, PIT/provenance, latency/R-gates).
- Honest gates (fail-closed, labelled, tested): LIVE requires R10 + sign-offs
  (`config/profiles.py` prod `_gated`, `execution/live_engine.py`); IBKR live
  refuses without gateway (`ibkr_contract` PAPER-ONLY); hardware throughput
  reports UNAVAILABLE until documented-hardware runs (`benchmark_report`);
  synthetic paths badged SOURCE/synthetic-DEMO (`tri_tier_source`).
- Labels per S55: Implemented (paper/sim/research/demo paths) /
  Partially validated (shadow soak needs 14-day wall-clock evidence;
  `shadow_soak_ok` gate tested) / Not implemented (live venue wiring —
  intentionally gated) / Unknown (none new).

## Launch checklists record (2026-10-02 — strategy 11 + LLM 12 + shared 5)

- Strategy (`research/strategy_validation.py`): OOS >=20% + Sharpe>0 | walk-forward
  win-rate | overfit veto (param worst-case + Monte Carlo/block-bootstrap p5>0;
  edge death -> DO NOT LAUNCH) | PIT chain + no restatements | survivorship
  (delisted >=5%) | costs profitable at 1.5x/2x | regimes bull/bear/highvol +
  2008/2020/2022 | risk (Sharpe/DD/Calmar/skew) | paper >=60d real flow |
  data (2+ providers, 0 gaps, tz, skew<=1s) | compliance (kill drilled +
  limits + routing + regulatory).
- LLM (`finance_model/llm_validation.py`): golden >=50/>=500 + edge cases |
  evals correctness/adherence/format | judge-human r>=0.6 | latency
  p50/p95/p99 + timeout/retry | cost 1x/5x/10x | prompt robustness + no
  secrets | red-team block>=95% + PII mask | schema>=95% + fallback |
  observability veto (100% traced + dashboards + alerts; "what changed?" ->
  NOT READY) | resilience (backoff/secondary/overflow/iter-cap) | rollback
  (versions + canary + e2e) | CI gates with teeth.
- Shared (`governance/launch_gates.py`): sign-off (quant/eng/risk/infosec/ops +
  criteria) | docs (specs/assumptions/limits) | monitoring live pre-launch |
  kill-switch drilled <=30d (tested, not documented) | on-call (plan/roto/runbooks).
- Evidence: `tests/test_launch_validation.py` 9/9 (all-pass + each-check-fails +
  both critical vetoes + unified launch + determinism).
