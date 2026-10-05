# DELTA — Complete AI Quantitative OS Plan (Single File)
# DELTA COMPLETE MASTER PLAN — v1.0 2026-10-05

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development (recommended)
> or executing-plans to implement this plan task-by-task.

**Goal:** Build DELTA into a closed, measurable, evidence-producing AI quantitative
operating system for professional traders and assisted users on one shared truth
(same data, same models, same risk, same audit — only presentation differs).

**Architecture:**

```text
USER → DELTA TUI (COMMAND / AI / DATA systems)
  → DELTA RUNTIME (Research | Decision | Execution)
  → OMS → PAPER / SHADOW / BROKER → RECONCILE
  → OUTCOME + ATTRIBUTION → MEMORY / REGISTRY → NEXT EXPERIMENT
```

**Tech Stack:** Python `delta_tui/` (canonical frontend, Textual+Rich, typed viewmodels),
Rust `tui/` (perf lane, Ratatui), `core/command_bus.py`, SQLite registries,
`core/vault.py` AES-256-GCM. OpenCode is a UX reference only — never a dependency.

**Status labels (honest, per directive S55):**
`Implemented` = code + tests + wired. `Partial` = code exists but contract
unenforced or unwired. `Missing` = no implementation. `Stub` = placeholder that
refuses or is sim-only.

**Non-goals:** No live-capital claims before R10 sign-off. No 200-indicator
expansion before OOS proof. No UI polish before the data-truth layer. No
`10M ops/s` claims before documented-hardware benchmarks.

---

## 0. Verified starting point (2026-10-05, STATUS v1.9: 929 passed)

Strong: 7-timestamp PIT (`core/domain/canonical.py:62-104`,
`data/tick_pit/timestamps.py:32-46`, `data/pit/factory.py`, `data/pit/query_engine.py`),
corp-action logic, 2 quality validators, versioned feature store,
ML zoo (OLS/Ridge/Lasso/RF/GBM/AR/Quantile + LSTM/Transformer CPU),
alpha contract+lab+DSR/PBO/CPCV, HMM/Bayesian/MS regime, 7 portfolio optimizers,
firewall/predictive separation, purged walk-forward, SQLite experiment/model
registries with `reproduce(EXP-ID)`, `core/vault.py`, `storage/event_store/store.py`.

Weak: no unified `DataPoint` enforcement at pipeline entry
(`core/canonical_pipeline.py:318-360` seeded path, no PIT-join);
`data/market/canonical.py:11-38` degraded stamps; news novelty/materiality are
`0.0` pass-throughs (`data/news/trust.py`); tool registry without schema/approval/audit;
`DecisionEngine` never emits `NO_TRADE`; backtester delegates costs to caller;
no `DeltaBench`; `SHADOW` = `PAPER` alias (`config/mode.py:35`) with no 14-day soak;
benchmarks report `UNAVAILABLE`; no OMS MMap journal with RTO/RPO proof;
drift is screening-only.

---

## A. Architecture freeze — Partial

Exists: `DELTA_VNEXT_PLAN.md` (frozen, 30/30 groups), `docs/adr/0001-0007`,
`core/command_bus.py`, `config/mode.py` (LIVE/PAPER/SIMULATION/RESEARCH/DEMO).

Build — one authoritative doc per subsystem:

```text
docs/SYSTEM_ARCHITECTURE.md
docs/DATA_ARCHITECTURE.md
docs/AI_ARCHITECTURE.md
docs/ML_ARCHITECTURE.md
docs/RESEARCH_ARCHITECTURE.md
docs/EXECUTION_ARCHITECTURE.md
docs/RISK_ARCHITECTURE.md
docs/MODEL_LIFECYCLE.md
docs/SYSTEM_STATUS.yaml
```

Every subsystem records
`DESIGNED / IMPLEMENTED / TESTED / BENCHMARKED / VALIDATED / PAPER / SHADOW / PRODUCTION`.
Never write `implemented` for a prototype. Verify: `SYSTEM_STATUS.yaml` parsed in CI;
any PRODUCTION claim without prior gates fails the build.

## B. Data foundation (P0) — Partial

Exists: `core/domain/canonical.py:62-104` SevenTimestamps + `is_usable_at`,
`data/tick_pit/timestamps.py:32-46`, `data/point_in_time/store.py:9-50`,
`data/pit/factory.py:25-60,90-160`, `data/pit/construction_pipeline.py:67-166`,
`data/pit/query_engine.py:54-138`, `data/pit/gate.py:11-13`,
`data/security_master/master.py:25-83`, degraded `data/market/canonical.py:11-38`.

Build:

```text
data/raw/ data/normalized/ data/pit/ data/market/ data/fundamentals/
data/macro/ data/news/ data/corporate_actions/ data/microstructure/
data/alternative/ data/features/ data/datasets/
```

Canonical record:

```text
DataPoint(symbol, event_time, publication_time, received_time, effective_time,
  source, revision, dataset_version, quality)
```

Mandatory guarantee: `t_event ≤ t_pub ≤ t_avail ≤ t_dec ≤ t_exec`. Information
published at 15:30 must never inform a 15:00 decision even if present in the DB.
Enforce the PIT-join inside `core/canonical_pipeline.py` (replace/augment the
seeded `fetch_market_bars` path) and upgrade `data/market/canonical.py` to full
stamps. Verify: 10-attack adversarial PIT suite (future price/earnings/revision/
macro/corp-action/universe/target/contamination/future-bar/overlap) +
shuffle-timestamp + embargo tests + `reproduce(EXP-ID)` hash-equal.

## C. Corporate actions — Implemented-logic / Partial-wired

Exists: `data/tick_pit/corporate_actions.py:22-338` (9 ActionTypes),
`data/ingestion/corporate_actions.py:8-91`, `data/security_master/corporate_actions.py:93-238`,
PIT-safe adjust `data/pit/factory.py:161-187`, timing guard `data/pit/leakage.py:109-118`.

Build: splits, dividends, mergers, spinoffs, symbol changes, delistings, rights
issues; PIT universe membership (`listed_date` fail-closed already in `master.py`);
documented adjustment choices (back-adjust vs ex-gated). Verify: split/dividend/
merger unit tests + `applied_at < ex_date` guard test.

## D. Data quality engine — Implemented, gate Missing

Exists: `data/tick_pit/data_quality.py:91-424` (13 issue types),
`data/market/quality.py:66-457` (EXCELLENT→UNUSABLE), `data/engineering/gates.py:20-25`,
`data/market/exchange_calendar.py:1-143` (NYSE/NASDAQ), `data/market/fundamentals.py:35-91`
fail-closed refusal.

Build: `DataQualityReport(PASS/WARN/FAIL)` covering missing values, duplicates,
timestamp errors, out-of-order events, price jumps, volume anomalies, bad corp
actions, stale data, source disagreement, schema violations. A FAIL dataset must
raise and never enter training — wire the gate into the training and promotion
paths. Add quarantine path + review queue + trend dashboard. Verify: FAIL fixture
refuses training with reason logged.

## E. Feature engine — Implemented

Exists: `data/market/feature_engine.py:50-67,298-468` (FeatureDefinition + lineage +
30+ Return/Vol/Momentum/RSI/MACD), `data/features/store.py:48-150`
(indexed by `(symbol,t_available)` + versions), `data/ingestion/features.py:6-7` sha16.

Build categories: PRICE, VOLUME, VOLATILITY, MOMENTUM, MEAN_REVERSION, TREND,
LIQUIDITY, MICROSTRUCTURE, FUNDAMENTAL, MACRO, NEWS, CROSS_SECTIONAL, REGIME.
Every feature carries `feature_id/formula/inputs/lookback/timestamp-rule/PIT-rule/
version/owner/tests`. Rule: prove incremental OOS information per feature; do not
add indicators for coverage. Verify: ablation + neutralization + decay tracking.

## F. Label engine — Missing

Only leakage guards exist (`data/pit/leakage.py:89-106`). Build:
`future_return_1d/5d/20d`, `future_volatility`, `direction`, `drawdown`,
`tail_loss`, `risk_adjusted_return`, event-based labels, triple-barrier labels,
with overlap/embargo handling, all PIT-aligned. Verify: future-label fixture fails
leakage tests; train/test contamination test green.

## G. Quantitative ML stack — Implemented

Exists: `quant/forecasting/models.py` (OLS/Ridge/Lasso/RF/GBM/AR/Quantile/Ensemble/
MultiHorizon + chronological `walk_forward_mse`), `quant/forecasting/deep.py`
(LSTM lookback-20 + Transformer, seeded CPU, train-only scaling),
`models/model_zoo/factory.py/registry.py/evaluation.py` (purged splits, honest
`SCREENING ONLY` tags).

Layers: (1) baselines Linear/Ridge/Lasso/Logistic/RF/XGB-LGBM-class,
(2) ARIMA/GARCH/state-space/Kalman, (3) MLP/LSTM/GRU/TCN/Temporal-Transformer,
(4) multi-task temporal, cross-asset attention, regime-conditioned, probabilistic.
Rule: every advanced model ships a baseline comparison and must win OOS.
Defer GPU trainer. Verify: `compare_models` artifact per experiment.

## H. Alpha engine — Implemented

Exists: `research/alpha_contract.py` (metadata + hash + no-demotion promote +
rank_ic), `research/alpha_factory.py` (purge=1/embargo=1 + manifest),
`research/alpha_lab.py` (10 families + orthogonalize + half-life + capacity ladder
+ DSR/PBO report), `quant/alpha/research.py` (5 hypotheses + IC/ICIR/Sharpe/
turnover/capacity/decay), `research/real_loop/model_lifecycle.py` (no-skip).

Maintain inventory `candidate / validated / shadow / active / retired` with
hypothesis, universe, frequency, decay, turnover, capacity, neutralization, IC,
ICIR, OOS-IC, cost-adjusted Sharpe, drawdown, failure modes. Verify: decay
auto-demotion, capacity-breach retirement, `alpha compare A B` same-period /
same-cost / same-universe.

## I. Regime intelligence — Implemented (unify)

Exists: `quant/regime/` full distribution stack (`regime.py`, `detector.py`,
`classifier.py`, `hmm.py`, `hmm_enhanced.py` posterior/credible, `bayesian_state.py`,
`markov_switching.py`, `regime_forecaster.py`); point-only in
`research/real_loop/regime.py` and `world_model/state/regime_state.py`.

Build single `RegimeDetector → P(BULL/BEAR/HIGH_VOL/RANGE/CRISIS)` + transition
matrix + confidence + persistence + shift alerts with false-positive accounting +
regime-conditioned allocation + human override with logged reason. Test whether
conditioning improves OOS; if not, remove it. Verify: regime on/off ablation.

## J. News intelligence — Partial

Exists: `delta_os/data_router.py:247-292` (RSS + title-hash dedup + lexicon +
`$TICKER` entities + catalysts + clickbait flag, fail-closed),
`quant/sentiment_nlp.py` (lexicon + dedup + batch), `data/news/trust.py`
(quarantine + prompt-injection regex only).

Missing: novelty scorer, materiality/impact model, real NER. Build full chain:
source-validate → dedup → timestamp-norm → entity → security-map → classify →
sentiment → novelty → materiality → horizon → market-impact. Store
`NewsEvent(article_id/source/published_at/received_at/securities/event_type/
sentiment/novelty/materiality/confidence)`. Train `event + context → future return
distribution`, never bare-LLM bullish. Verify: dedup hash test + impact
calibration + quarantine test.

## K. Finance AI role — Partial

Finance AI handles financial reasoning, research synthesis, tool selection,
hypothesis generation, experiment planning, news interpretation, portfolio/risk
explanation, report generation. It is one component — never the numerical alpha,
never order authority. Build the authority-boundary doc + refusal tests.
Verify: LLM order attempt refused by deterministic layer.

## L. FM training fixes — Partial/Broken (exact file: `finance_model/training/qlora.py`)

1. Response-only loss — Missing: `_tokenize_dataset:114` sets
   `labels = input_ids` (learns the prompt). Fix: mask SYSTEM/USER/QUESTION
   to -100, loss on ANSWER only, with a collator test.
2. QLoRA config — OK: `build_quantization_config:45-66` correctly gates on
   CUDA + bitsandbytes, bf16-vs-fp16 by capability.
3. Precision — Broken: `TrainingArguments:231-232` hardcodes fp16/bf16 False.
   Fix: agree with hardware capability, tested.
4. Gradient checkpointing — Missing: declared in `collator.py:28`, never
   enabled/tested. Fix: enable + memory test.
5. trust_remote_code — Broken: hardcoded `True` (`:131`, `:198`).
   Fix: explicit opt-in flag, default False.
6. Dataset versioning — Partial: `reproducibility.py` seeds + `run_registry.py`
   exist. Fix: per-run `dataset_hash/model_rev/tokenizer_rev/git_commit/
   config_hash/seed/hardware/precision` manifest.

## M. FM dataset — Partial

Exists: `data/finance_grounded/` 174 rows (S1/S2-oracle/S3-refusal) +
640 SFT rows. Build 14 categories (FINANCIAL_STATEMENTS, VALUATION, MACRO,
MARKET_STRUCTURE, RISK, PORTFOLIO, EXECUTION, QUANT_RESEARCH, TIME_SERIES, NEWS,
FINANCIAL_MATH, BACKTEST_ANALYSIS, FAILURE_ANALYSIS, TOOL_USE) with
`GOOD / BAD / WHY_BAD / CORRECTED / EVIDENCE` shapes; teach abstention when
information is insufficient. Verify: refusal-shape + oracle-parity tests.

## N. Tool-use AI — Partial

Exists: `finance_model/tools/contracts.py` (READ_ONLY/SIMULATION/SENSITIVE +
ToolRequest/ToolResult), `registry.py` (duplicate-guard), `router.py:6-48`
(read-only allowlist + `MAX_CONTEXT_TOKENS` truncate),
`research/agent/tool_registry.py` (basic), `delta_os/opencode_tools.py` bridge.

Missing: JSON-schema arg validation, SENSITIVE/SIMULATION approval workflow,
audit log, idempotency enforcement (`request_id` carried only). AI calls
`market_data / news_search / portfolio_state`, then synthesizes; it never touches
the broker. Verify: unknown-tool raises, sensitive needs approval, audit appended.

## O. Research agent — Partial

Exists: `research/agent/research_loop.py` + `tool_registry.py` + `permissions.py`.

Build `ResearchPlanner / HypothesisGenerator / DatasetBuilder / ExperimentRunner /
BacktestRunner / StatisticalValidator / FailureAnalyzer / ReportGenerator`
producing HYPOTHESIS → DATASET → PIT-CHECK → FEATURE → BASELINE → MODEL →
WALK-FORWARD → COSTS → STATISTICS → STRESS → REPORT with budgets.
Example prompt "momentum in high-vol regimes" must yield a hashed manifest
end-to-end. Verify: one-command hypothesis-to-report test.

## P. Portfolio engine — Implemented

Exists: `quant/portfolio/optimizer.py` (MV/BL/Risk-Parity/HRP/CVaR/Min-Var/Max-Div),
`research/real_loop/portfolio_risk.py` (true CCD RP), `portfolio/factor_optimizer.py`
+ `budget.py`, `delta_omega/portfolio_exec.py` (Almgren-Chriss).

Optimize over expected-return, risk, uncertainty, correlation, turnover, costs,
liquidity, factor exposure, concentration, leverage, tail risk; compare MV, Risk
Parity, CVaR, Black-Litterman, factor-constrained, robust empirically with hard
(not advisory) constraints. Verify: determinism test + infeasibility explanation +
snapshot reconstruct.

## Q. Risk engine — Implemented / Partial

Firewall (deterministic, pre-network, fail-closed): `risk/firewall/firewall.py:43`,
`risk/pre_trade/validation.py`, `risk/limits/limits.py`, wired via
`execution/engine/engine.py`, `core/oms/gateway.py:39`, `delta_os/safety.py`.
Predictive (advisory): `risk/analytics/var.py` (hist VaR/CVaR),
`risk/stress/stress_engine.py`, `quant/risk_engine.py`. EVT / liquidity-VaR /
correlation-breakdown unverified — do not claim.

Rule: the model recommends, the firewall vetoes, never the inverse.
Verify: ML-approve + firewall-reject → rejected, with `risk_evidence_missing /
mismatch` paths tested.

## R. Decision engine — Partial

`decision/decision.py:14` defines NO_TRADE; `decision/engine.py:57` only emits
WAIT (utility `U = ER − risk − cost`, confidence < 0.50 → WAIT).
Duplicates define NO_TRADE in `finance_model/decision_policy.py:35`,
`uncertainty.py:24`, `quant/uncertainty/engine.py:106`.

Build canonical semantics: NO_TRADE = policy/risk block, WAIT = low confidence.
Fuse prediction + portfolio + risk + costs + liquidity + regime + execution
conditions into BUY / SELL / HOLD / NO_TRADE. Verify: NO_TRADE path test with
reason codes.

## S. Backtesting engine — Partial

Exists: `simulation/backtest/engine.py:75` + `replay/` + `discrete_event/` +
`market_simulator/` (matching/book/queue/adverse-selection/fees) +
`simulation/costs/model.py` + `execution/impact/` + `cost_engine.py`.
Thin: `backtest/microstructure/` (2 files); costs delegated to caller handler.

Build event-driven market → feature-availability → inference → decision → order →
queue → execution → fill → portfolio, modelling spread, slippage, fees, latency,
partial fills, market impact, liquidity, order queue. Verify: sim == backtest
parity harness at identical costs.

## T. Statistical validation — Implemented

Exists: `quant/validation/robust.py` (purged splits + exact Bailey DSR +
CSCV-PBO S=16 + reality-check), `delta_omega/alpha_risk.py`,
`research/statistics/canonical.py`, `validation/walk_forward/splitter.py`
(purge=1/embargo=1) + ladder R2, `validation/evidence_ledger.py`.
Do not cite the legacy top-half proxy as PBO.

Mandatory: train/test separation, walk-forward, purged CV + embargo, CPCV,
bootstrap, permutation, multiple-testing correction (FDR/Bonferroni), PBO,
Deflated Sharpe. `backtest Sharpe > 1` alone never validates. Verify: thresholds
enforced in promotion code + validation-report artifact per experiment.

## U. DeltaBench — Missing

Zero hits for `DeltaBench` on disk. Distinct from FinBench (LLM-only:
`finance_model/finbench.py`, `evaluation/finbench_metrics.py`,
`evaluation/delta_gates.py` G1-G16).

Build `DeltaBench/prediction / finance_reasoning / news / risk / portfolio /
research / tool_use / adversarial / regression/` with task-appropriate
accuracy/precision/recall/MAE/RMSE/log-loss/Brier/calibration/IC/ICIR/Sharpe/
Sortino/drawdown/turnover/cost-adjusted-return. Every new model must report here.
Verify: CI regression gate.

## V. Model registry — Implemented

Exists: `provenance/model_registry.py` (RESEARCH→VALIDATED→PAPER→SHADOW→PROD→
RETIRED + promote gates) + `experiment_registry.py`,
`research/ledger/sqlite_registry.py` (+ identity/experiment/result),
`research/model_lifecycle.py`, `finance_model/registry/promotion.py`.

Lifecycle TRAINING → CANDIDATE → VALIDATED → SHADOW → APPROVED → ACTIVE →
RETIRED with model version, dataset, features, architecture, hyperparameters,
training/validation/OOS periods, metrics, failure cases, calibration, approval.
Verify: skip-promotion refused; `reproduce(EXP-ID)` verifies manifest hash.

## W. Experience / research memory — Implemented-store / Partial-loop

Exists: `memory/experience/experience.py:12` (+ store/retrieval/failures),
`learning/` (closed_loop + attribution + adaptation gate + protected failures),
`research/memory/vector_index.py` (522-line vector+graph retrieval).

Store Experiment/Hypothesis/Dataset/Features/Model/Result/Failure/Reason/Decision
— not chat history. Retrieve "already tested momentum+RSI in this regime" with
prior EXP-ID; auto-propose next hypothesis from failures (Group29 thin — harden).
Verify: repeat-failed-idea warns with prior experiment.

## X. Shadow trading — Partial

Exists: `deployment/shadow.py:16` (record/evaluate/PROMOTE-HOLD-REJECT),
`ops/shadow_validate.py`, `validation/long_duration.py` (10k bars),
`trading/paper/paper_engine.py`. But `config/mode.py:35` aliases SHADOW→PAPER.

Build true LIVE-DATA → PREDICT → DECIDE → HYPOTHETICAL-EXEC → REAL-OUTCOME,
measuring prediction error, decision quality, execution assumptions, latency,
turnover, drawdown, regime splits. Add mirror-diff thresholds + 14-day
zero-downtime soak. Verify: wall-clock soak artifact (the one wall-clock gate
that cannot be unit-tested).

## Y. Performance engineering — Partial

Exists: `benchmarks/framework.py` + `kernel_bench.py` + `latency_suite.py`,
`benchmark/runner.py`, `BENCHMARKS.md`, Java plane memo (14.2M ring ops/s,
13.3µs p50 loopback). P0 Sprint6 targets (LOB 10M/s, firewall <7µs) report
`UNAVAILABLE` until documented-hardware runs — correct, keep honest.

Process SOURCE → COMPILE → UNIT → BENCHMARK → PROFILE → OPTIMIZE → BENCHMARK-AGAIN
for throughput, p50/p95/p99/p99.9, memory, CPU, allocations. Never claim before
measuring. Verify: published bench JSON on documented hardware.

## Z. Production-grade local app — Partial

Python `delta_tui/` is canonical (VNEXT freeze); Rust `tui/` is the perf lane.
HOME must answer happening / changed / belief / confidence / risk / portfolio /
attention — not a chatbot splash (`delta_tui/screens/home.py`, `tui/src/views/home.rs`
are splash-only today). Decision card per idea: expectation, P(positive),
95% interval, regime + confidence, evidence for/against, portfolio effect
(sector exposure, marginal VaR, correlation), execution (cost, liquidity), risk
(concentration, tail-loss), decision state (REVIEW/HOLD/NO-TRADE/ELIGIBLE), model
version, data-as-of timestamp. Professional and Assisted share truth.
Verify: `NO_DEMO_STATE` suite stays green; every number carries
SOURCE / AS-OF / FRESHNESS / CONFIDENCE.

## Z+. Missing control layers (not shortcuts — required)

1. Unified state + event sourcing: `storage/event_store/store.py` (append/replay)
   + `portfolio/state.py` + `observability/audit_chain.py` exist. Missing: OMS
   MMap write-ahead journal (CREATED→VALIDATED→RISK_APPROVED→SUBMITTED→
   ACKNOWLEDGED→FILLED), kill-9 → replay → snapshot → broker-poll → 3-way
   reconcile, RTO<60s RPO=0 (P0 Sprint4), past-allocation reconstruct wired to replay.
2. Model risk: central feature+prediction+regime drift monitor → Models screen +
   auto-demote (today only `finance_model/datasets/drift.py` PSI screening;
   `quality_gate.py:36` explicitly no drift); disagreement engine consuming
   `model_disagreement`; uncertainty/calibration gate blocking sizing when
   uncalibrated; per-pipeline latency/accuracy budgets.
3. Security: vault `core/vault.py` done. Add rotation, RBAC beyond
   `DELTA_UNLOCK_TOKEN` (`governance/kill_switch.py` shim must bind to board
   `:21-30`; `security/adversarial.py` is a skeleton suite), prompt-injection
   suite, secrets masking, provider-fallback/offline mode, update rollback plan.
4. Hierarchical kill: GLOBAL/strategy/broker on one board; monthly drill logged;
   `Ctrl+X K` + `/kill CONFIRM` bypasses LLM (`delta_tui/keymap.py:28`).
5. Evidence graph: extend manifest hashes into a
   dataset→feature→model→experiment→decision→outcome→attribution graph.

## Build order (frozen — do not reorder)

Stage 1 Foundation (P0): A → B → F → D-gate → C-feed.
Stage 2 Quant brain (P0): E-OOS → G-baseline-rule → H → I-ablation → J-min → K → L → M-min.
Stage 3 Research→Decision (P0/P1): N → O → P → Q-veto-test → R + state journal.
Stage 4 Validation (P0): S-harness → T-enforce → U-DeltaBench → V → W-link → evidence graph → drift monitor.
Stage 5 Reality (P1/P2): X-soak → security/offline/rollback → TUI UI-1→UI-5 (separate file) → Y-measure.
P3 future: FIX, multi-broker, exchange connectivity, vendors, SOR, co-location, FPGA, 24/7, regulatory.

P0 complete = canonical+PIT+provenance+versioning+feature/label+baseline+neural+
regime+FM+tools+backtest+WF+leakage+stats+DeltaBench+registry+firewall+optimizer+
shadow-harness. P1 adds full news, multimodal, probabilistic, calibration, agent,
memory, failure intel, simulator, impact, advanced portfolio. P2 = Rust/LOB/codec/
IPC/GPU/parallel. P3 = institutional expansion.

Terminal is the interface — order DATA → VALIDATION → AI/ML → RESEARCH →
DECISION → RISK → EXECUTION → UI.

## Verification + risks

Per-stage: PIT adversarial + manifest hash; baseline-beats-advanced; firewall-veto;
NO_TRADE path; sim parity; DeltaBench CI; soak artifact; DR RTO/RPO; bench JSON;
NO_DEMO_STATE green. Biggest risk: UI before truth → polished unreproducible
numbers (keep feature freeze until Stage 1 green). Live stays
`ERR_LIVE_PROHIBITED` until R10 sign-off. All Stage 1–4 changes additive; rollback
via registry demote/retire + reproduce.
