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
- [ ] Remove duplicate active launch paths (delta.py single entry; shims warn)
- [ ] Define package dependency rules (tui->controllers->domain, never reverse)
- [ ] Create architecture dependency graph (automated import-lint)
- [ ] Define bounded contexts (data/alpha/world/portfolio/risk/execution/research)
- [ ] Define domain ownership (one owner module per context)
- [ ] Define public interfaces per context (`__init__` exports only)
- [ ] Define serialization contracts (viewmodels frozen dataclasses)
- [ ] Define event contracts (store events typed)
- [ ] Create architecture decision records (`docs/adr/`)

### GROUP 02 — Repository hygiene [P0-remainder]
- [ ] Remove tracked `__pycache__` / `.pyc` from git
- [ ] Remove stale generated trees (`DELTA_TREE.txt` regenerated, not tracked stale)
- [ ] Remove zero-byte scripts
- [ ] Archive obsolete documents (keep plan files, archive duplicates)
- [ ] Consolidate duplicated roadmaps (this file authoritative)
- [ ] Create one authoritative ROADMAP.md (pointer to this file)
- [ ] Create one authoritative STATUS.md (P0 green + next slice)
- [ ] Version documentation (doc header: version/date/status)
- [ ] Add architecture linting (import-linter or equivalent CI check)
- [ ] Add tracked-cache pre-commit guard

### GROUP 03 — Configuration [P0-remainder]
- [x] Central mode schema (`config/mode.py`: LIVE/PAPER/SIM/RESEARCH/DEMO)
- [ ] Environment profiles (dev/paper/shadow/prod yaml)
- [ ] Research configuration (dataset/seed/budget block)
- [ ] Simulation configuration (venue policies, latency, impact)
- [ ] Paper configuration (broker paper endpoints, limits)
- [ ] Shadow configuration (mirror + diff thresholds)
- [ ] Production configuration (gated, signed, R10 only)
- [ ] Configuration hashing (sha of effective config per run)
- [ ] Runtime configuration snapshots (stored with experiment manifest)
- [ ] Configuration compatibility tests

### GROUP 04 — CLI foundation [P0-done, harden]
- [x] One delta executable (`apps/cli/delta.py`)
- [x] One interactive TUI (`delta_tui.app.DeltaApp`)
- [x] One command registry + parser + palette
- [x] One natural-language router (slash + NL converge on action model)
- [ ] One permission layer (kill/risk bypass LLM; write ops need confirm)
- [ ] One session manager (new/resume/fork/export/search/persist)
- [ ] One event stream (store.publish typed events)
- [x] One view-model layer (`delta_tui/viewmodels/models.py`)
- [x] One terminal state store (`delta_tui/state/store.py`)
- [ ] Delete duplicate command implementations (audit Typer vs registry)

### GROUP 05 — TUI framework [P0-done, harden]
- [x] Adopt Textual as primary TUI (+ Rich fallback)
- [x] Create `delta_tui/app.py` controller
- [x] Create screen registry (14 ids incl. book alias)
- [x] Create widget registry (`delta_tui/widgets/`)
- [x] Create responsive layout engine (`responsive.py`)
- [x] Create theme engine (`themes.py`)
- [x] Create keyboard manager (`keymap.py`: Ctrl+P palette, Ctrl+X leader)
- [x] Create command palette
- [ ] Create modal manager (confirm kill, inspect alpha lineage)
- [ ] Create notification/toast manager (breach, fill, experiment done)

### GROUP 06 — TUI design system [P0-done, harden]
- [x] Typography / spacing / panel / table system (Rich renderables)
- [x] Status-chip system (DATA/MODEL/BROKER/KILL/latency)
- [x] Alert system (risk breach, stale data)
- [x] Numeric-format system (`Number` viewmodel with fmt)
- [x] Positive/negative semantics (theme-driven)
- [x] Provenance badges (mode + source/as-of on every screen)
- [ ] Accessibility/high-contrast mode
- [ ] No-color mode + unicode fallback
- [ ] Screen-reader-friendly output (plain-text render path per screen)
- [ ] Design-system doc (`docs/tui-design.md`)

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
- [ ] Deep-link: selecting alpha opens lineage graph (Enter)

### GROUP 08 — Responsive terminal [P0-done, verify on hardware]
- [x] 160-col full workstation layout
- [x] 140/120/100-col degrade rules
- [x] 80-col collapsed sidebar/context
- [x] Compact + SSH/small-terminal mode
- [ ] No-color mode
- [ ] Screen-reader output verified
- [ ] Unicode fallback verified (Windows cp1252 safe)
- [ ] Width snapshot tests
- [ ] Resize handler (reactive reflow)
- [ ] `delta doctor --display` capability probe

### GROUP 09 — Command UX [P0-done, extend]
- [x] `/` palette + subcommand/argument completion
- [x] Symbol/venue/model/experiment completion
- [x] Context-aware help + history + aliases
- [ ] `/book SYM --depth N`, `/analyze SYM --horizon`, `/scenario NAME`
- [ ] `/alpha inspect|compare`, `/portfolio attribution|optimize`
- [ ] `/risk stress|reverse-stress`, `/execution SYM`, `/system latency`
- [ ] NL parity tests (NL == slash on same action model)
- [ ] Palette fuzzy-rank tests
- [ ] Unknown-command guidance (never empty)
- [ ] Kill command always bypasses LLM (tested)

### GROUP 10 — Sessions [P1]
- [ ] New session / resume session / session tabs
- [ ] Session rename / fork / export / search
- [ ] Session metadata (mode, universe, mandate hash)
- [ ] Session recovery (crash restore)
- [ ] Session persistence (SQLite, survives restart)
- [ ] Session-scoped research memory pointer
- [ ] Session audit trail linkage
- [ ] Multi-session isolation (risk state per session in SIM)
- [ ] Session diff (mandate/config drift)
- [ ] Session retention policy

### GROUP 11 — Market data [P1]
- [ ] Canonical tick/trade/quote/L1/L2/L3 models
- [ ] Venue metadata (fees/rebates/tick/lot/session)
- [ ] Market calendar (open/macro events/close)
- [ ] Symbol master (mappings/delistings)
- [ ] Data freshness model (as-of/staleness per feed)
- [ ] Tri-tier router (live -> cache -> synthetic) with explicit badges
- [ ] LRU cache with TTL + stats surfaced in System screen
- [ ] Yahoo/free-tier adapters with degraded badges
- [ ] Feed health state machine (HEALTHY/DEGRADED/DOWN)
- [ ] Bad-tick / gap detection wired to alerts

### GROUP 12 — PIT [P1, first quant gate]
- [ ] Observation / publication / knowledge / revision timestamps
- [ ] PIT joins (no future leakage by construction)
- [ ] PIT universe (point-in-time membership)
- [ ] PIT fundamentals / corporate actions / macro
- [ ] Automated leakage tests (shuffle-timestamp + embargo tests)
- [ ] Dataset snapshots + SHA manifests
- [ ] Train/validation/OOS period enforcement
- [ ] Revision handling (restatement-aware)
- [ ] PIT audit per experiment (dataset SHA in manifest)
- [ ] `delta research reproduce` replays PIT exactly

### GROUP 13 — Data engineering [P1]
- [ ] Raw -> normalized -> feature lake layout
- [ ] Snapshot manifests + dataset hashes
- [ ] Partitioning (symbol/date) + compression
- [ ] Data retention policy
- [ ] Dataset catalog + lineage (dataset -> features -> experiment)
- [ ] Backfill tooling with provenance stamps
- [ ] Corporate-action adjustment pipeline (documented choices)
- [ ] Survivorship-bias controls
- [ ] Data version compatibility checks
- [ ] Lake integrity cron (hash re-verify)

### GROUP 14 — Data quality [P1]
- [ ] Missing/duplicate detection, timestamp + sequence validation
- [ ] Cross-feed reconciliation, bad-tick / volume / price anomaly flags
- [ ] Feed-gap detection + quality scoring per symbol/day
- [ ] Quarantine path (bad slices excluded with reason logged)
- [ ] Quality badge on Market/Security screens
- [ ] Quality-gated research (below-threshold data blocks promotion)
- [ ] Anomaly review queue
- [ ] Calibration of thresholds from history
- [ ] Quality trend dashboard
- [ ] Quality incident audit

### GROUP 15 — Reference data [P1]
- [ ] Security/exchange/currency masters, contract specs
- [ ] Tick-size / lot-size tables, trading sessions
- [ ] Corporate actions + symbol mappings + delisting DB
- [ ] Venue fee/rebate schedule table (SOR input)
- [ ] Reference-data versioning (hash per release)
- [ ] Effective-dating (as-of joins)
- [ ] Corporate-action unit tests (splits/dividends/mergers)
- [ ] Stale-reference alerts
- [ ] Reference diff tool
- [ ] Reference sign-off in certification gate

### GROUP 16 — Microstructure [P1]
- [x] Event clock + L1/L2/L3 books + price-time priority (foundation)
- [x] Venue replace policies (RETAIN_IF_DECREASE/LOSE/NEW)
- [ ] Queue position / queue-ahead-qty (done for L3; extend L2)
- [ ] Partial fills + cancel/replace state machine
- [ ] Matching engine parity tests (price-time oracle)
- [ ] Venue-policy matrix per exchange (documented + tested)
- [ ] L2 gap / crossed-book invariants + recovery
- [ ] Replay harness: events -> book states deterministic
- [ ] Microstructure fidelity scorecard vs venue specs
- [ ] Book workspace wired to live/sim L2 (not static text)

### GROUP 17 — Queue/latency [P1]
- [x] Simulated vs compute latency split (foundation)
- [ ] Queue depletion / fill-probability models
- [ ] Network/gateway/strategy/risk/exchange latency breakdown
- [ ] Tail-latency (p99/p99.9) tracking, empirical calibration
- [ ] Latency histograms on System screen (modelled vs measured)
- [ ] Venue latency table (SOR input)
- [ ] Latency-stress scenarios (spike injection)
- [ ] SLA definitions + breach alerts
- [ ] Hardware-documented benchmark runs
- [ ] `measure_latency` never conflates CPU time with modelled latency (tested)

### GROUP 18 — Impact/cost [P1]
- [ ] Spread + temporary/permanent impact models
- [ ] Square-root + Almgren-Chriss + power-law + participation models
- [ ] Adverse-selection / toxicity inputs
- [ ] Cost calibration against paper/shadow fills (not stylized 50*sqrt)
- [ ] Cost uncertainty bands (not point estimates)
- [ ] Cost model versioned in experiment manifest
- [ ] Impact-aware SOR objective (expected shortfall, not fee-only)
- [ ] Post-trade cost attribution (Execution screen realized vs model)
- [ ] Cost-model drift monitor
- [ ] Cost sign-off in R6 gate

### GROUP 19 — Historical scenarios [P1]
- [ ] 1987 / 1998 / 2000-02 / 2008 / 2010 flash / 2015 / 2018 /
      2020 COVID / 2022 rates / modern liquidity shocks
- [ ] Scenario manifests (data slice + hash + rules)
- [ ] `/scenario NAME` one-command replay on Scenarios screen
- [ ] Scenario results comparable across strategies (same costs)
- [ ] Reverse-stress synthesis (find breaking scenarios)
- [ ] Scenario library versioned + cited in R4 gate
- [ ] Liquidity-shock injection (spread/depth multiplier paths)
- [ ] Correlation-break scenarios
- [ ] Scenario attributions (what broke: costs? crowding? regime?)
- [ ] Nightly scenario regression (main strategies)

### GROUP 20 — Alpha laboratory [P1]
- [ ] 10 families: momentum / mean-reversion / value / quality / carry /
      volatility / liquidity / event / stat-arb / microstructure
- [ ] Family registry with ownership + status (active/decay/retired)
- [ ] Alpha Lab screen family table (alphas/active/decay per family)
- [ ] Per-alpha lineage (features -> neutralization -> validation)
- [ ] Alpha retirement rules (decay + capacity + crowding triggers)
- [ ] Crowding-awareThrottling (not just IC rank)
- [ ] Alpha combination (ensemble allocator, not naive average)
- [ ] Capacity-scaled allocation (size the alpha, not just pick it)
- [ ] Alpha catalog versioned (ID immutable, versions explicit)
- [ ] Family coverage test (each family has >=1 validated alpha or explicit gap)

### GROUP 21 — Alpha science [P1]
- [ ] Cross-sectional ranking + beta/sector/industry/size/vol neutralization
- [ ] Orthogonalization + residual alpha paths
- [ ] Alpha combination + decay tracking (half-life per alpha)
- [ ] Neutralization unit tests (zero residual exposure by construction)
- [ ] Decay dashboard (Alpha screen DECAY column live)
- [ ] Neutralization choice logged in manifest (which factors, which window)
- [ ] Residual diagnostics ( автокор + turnover + concentration)
- [ ] Combination weight rationale (stored, not implicit)
- [ ] Decay-triggered demotion (auto to candidate pool)
- [ ] `alpha compare A B` same-period, same-costs, same-universe

### GROUP 22 — Statistical validation [P1]
- [ ] IC / ICIR + HAC inference + block-bootstrap CIs
- [ ] FDR / Bonferroni (multiple-testing discipline)
- [ ] DSR (definitive, not proxy) + CSCV/CPCV-based PBO (not top-half approx)
- [ ] Reality-check / SPA methodology for shortlisted alphas
- [ ] Embargo + purging in walk-forward splits
- [ ] OOS stability tests (regime-split IC: 2018-22 vs 2023-26 style)
- [ ] Validation report per experiment (stored artifact, hashed)
- [ ] Promotion thresholds documented + enforced in code
- [ ] Validation-method version in manifest
- [ ] Research screen shows validation stage honestly (pass/fail/pending)

### GROUP 23 — Capacity/crowding [P1]
- [ ] Capacity curves calibrated against execution data (replace stylized proxy)
- [ ] ADV participation / liquidity / turnover / cost scaling
- [ ] Alpha decay under size (capacity-conditioned decay)
- [ ] Crowding indicators (correlation crowding, consensus overlap)
- [ ] Capacity confidence intervals (not point capacity)
- [ ] Alpha retirement on capacity breach
- [ ] Capacity input to portfolio optimizer (size caps, not post-hoc)
- [ ] Capacity backtests (replay at 1x/5x/20x size)
- [ ] Capacity sign-off in R5 gate
- [ ] Capacity dashboard on Alpha screen

### GROUP 24 — World model [P1]
- [ ] HMM / Markov-switching / Kalman / state-space / Bayesian estimation
- [ ] Transition matrix + prediction + confidence + persistence stats
- [ ] Regime-conditioned allocation (world model -> portfolio weights)
- [ ] Regime labels on Market/Home screens with confidence
- [ ] Regime-shift alerts (with false-positive accounting)
- [ ] Regime-split validation (strategy must survive per-regime cuts)
- [ ] World-model version in manifest
- [ ] Model comparison (which regime model, why, evidence)
- [ ] Stress conditioned on predicted regime (not just historical)
- [ ] Regime override path (human + reason logged, audited)

### GROUP 25 — Forecasting/ML [P1]
- [ ] Linear / regularized / tree / GBM / temporal-CNN / temporal-Transformer
- [ ] Probabilistic + quantile forecasting + calibration plots
- [ ] Ensemble selection with honest validation (no selection bias)
- [ ] Feature registry (versioned, hashed, lineage to dataset)
- [ ] Model registry (versioned, promotion gates)
- [ ] Drift monitoring (feature + prediction + regime drift)
- [ ] Calibration enforced (uncalibrated models cannot size positions)
- [ ] ML experiment budget accounting
- [ ] Model cards per promoted model (data/validation/limits/risks)
- [ ] Model monitor on Models screen (health/drift/version live)

### GROUP 26 — Portfolio [P1]
- [ ] Mean-variance / Black-Litterman / risk-parity / HRP / CVaR /
      max-diversification / robust optimization
- [ ] Factor / liquidity / capacity constraints (hard, not advisory)
- [ ] Optimizer choice + constraints hashed in manifest
- [ ] Attribution (factor/sector/alpha sleeve) on Portfolio screen
- [ ] `portfolio optimize` constrained run with reason codes
- [ ] Turnover / trade-list output with cost preview
- [ ] Constraint-breach explanations (why infeasible, what relaxed)
- [ ] Multi-objective handling (return/risk/cost/turnover explicit)
- [ ] Optimizer determinism tests (same input -> same output)
- [ ] Portfolio snapshots versioned (reconstruct any past allocation)

### GROUP 27 — Risk [P1]
- [ ] Gross/net/factor risk + VaR/ES/liquidity-VaR/concentration/
      correlation-breakdown/reverse-stress/dynamic budgets
- [ ] Risk governor pre-trade (hard blocks, tested)
- [ ] Limit table live on Risk screen (use/limit per metric)
- [ ] Tail panel (VaR99/ES99/liq-VaR/reverse-stress summary)
- [ ] Breach-watch checklist (concentration/sector/factor/liquidity/margin/corr)
- [ ] Reverse-stress solver (what breaks us, how far away)
- [ ] Correlation-regime conditional limits (tighten when correlations spike)
- [ ] Risk-budget allocation + utilization tracking
- [ ] Kill-switch drill tests (monthly, logged)
- [ ] Risk sign-off in every promotion gate R1..R10

### GROUP 28 — Execution/OMS [P1]
- [ ] Order state machine (parent/child, cancel/replace, reconciled states)
- [ ] Idempotency + duplicate prevention (client-order-id discipline)
- [ ] Reconciliation loop (broker vs OMS, breaks surfaced on Orders screen)
- [ ] SOR on expected shortfall (spread/fee/rebate/depth/queue/fill-prob/
      latency/adverse-selection/toxicity/venue-health/order-type/urgency/state)
- [ ] FIX session: logon/heartbeat/test-req/resend/seq-reset/reject/
      business-reject/logout/gap-recovery/reconnect/replay/persistence/TLS/drop-copy
- [ ] Broker adapters (paper first; live only post-R10)
- [ ] Execution ticket widget (parent algo/status/venues/attribution)
- [ ] TCA loop (model vs realized, fed back to cost calibration)
- [ ] Execution realism gate R6 (simulated fills match venue stats)
- [ ] Execution audit (every fill: venue/price/fee/reason code)

### GROUP 29 — Research OS/Agent [P2]
- [ ] Tool registry (typed tools, schemas, budgets, permissions)
- [ ] Agent identity + research RBAC (who/what may run/promote)
- [ ] Hypothesis planner (hypothesis -> plan -> tool choice)
- [ ] Experiment scheduler (queue, budgets, priorities, preemption)
- [ ] Failure diagnosis (classify: data/leakage/cost/regime/crowding/code)
- [ ] Iterative loop: branch experiment -> compare -> reject/promote
- [ ] Research memory (hypotheses/experiments/results/decisions, searchable)
- [ ] Automatic evidence writeback (every run appends manifest + artifacts)
- [ ] Next-hypothesis proposer (conditioned on failures, e.g. liquidity-regime)
- [ ] Human-in-loop gates (promote/demote/retire need approval + reason)

### GROUP 30 — Production/evidence [P3+P4]
- [ ] Persistent experiment/model/feature registries (SQLite now, PG path open)
- [ ] Drift monitoring + observability (metrics/traces/SLOs)
- [ ] Reliability/chaos drills + security (SBOM/secrets/audit) + DR runbooks
- [ ] Native perf evidence: p50/p95/p99/p99.9 per kernel (LOB ins/cancel/
      replace/match, dedup, risk, ser) on documented hardware
- [ ] Rust = event transport/replay/serialization; C++ = hot microstructure
- [ ] Long-duration paper/shadow evidence (weeks, not hours)
- [ ] Formal R0->R10 certification ladder wired to gates:
      R0 Research, R1 Reproducible, R2 Statistical, R3 OOS, R4 Stress,
      R5 Capacity, R6 Execution, R7 Paper, R8 Shadow, R9 Candidate, R10 Production
- [ ] No R10 without all prior gates green + sign-offs
- [ ] Production change freeze + rollback plan
- [ ] Post-production review (what worked, what decayed, next hypotheses)

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
