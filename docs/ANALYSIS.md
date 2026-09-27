# DELTA — Complete Plan Analysis (top-quant review)

Date: 2026-09-25. Baseline: 72 unit tests. Now: 85+ with new coverage. Scope: paper/sim only, local/open LLM, Rust+C++.

## 1. What was broken

- ~50 zero-byte modules; `market_data` types missing so `feeds/replay.py` failed to import.
- `risk/` (firewall, limits, pre-trade, kill switch) and `execution/` (OMS, order state) empty while CLI claimed `risk_firewall: configured`.
- `brokers/simulator` drifted from `BrokerInterface` (`submit_order` vs `place_order`, UUID vs str).
- `quant/` had no `signals/` or `factors/`; optimizer equal-weight placeholder.
- `finance_model` rule-based only, no grounding.
- `data/`, `research/`, `config/`, `docs/` empty — Blocks 1/4 unimplementable.
- `simulation/costs` defaults 0 (forbidden by plan); no PIT store, no experiment registry.
- `validation/` splitter/OOS/regression empty; only unit tests existed (no integration/replay/security/chaos/perf/e2e).
- `rust/` checksum demo only; no FFI boundary.
- `DELTA.docx` v1.0 qualitative only: no schemas, cost formulas, risk numbers, TTLs, latency budgets, hardware pins, FIN-Bench rubrics, promotion gates, FFI ABI, LLM routing.

## 2. What was implemented (this pass, in dependency order)

0. Hygiene: `schemas/__init__` + `schemas/events`, `config/paper.yaml` (limits-v1), `pyproject` (ruff/mypy/markers, validation tests in scope), `data/__init__`, `tests/__init__`.
1. Data: `Quote/Trade/Bar/OrderBook/MarketSession`, `Normalizer` (duplicate drop, lineage hash), `validators`, `QualityReport/dataset_hash`, `data/point_in_time/store.py` (as-of, dataset hash).
2. World model: `StateFusion.state_hash` + canonical ordering (build API unchanged).
3. Quant: `quant/signals/momentum.py` (momentum, zscore), `quant/factors/cross_section.py` (ranks).
4. Research: `simulation/costs/model.py` (commission+spread+slippage+sqrt-impact+fees, non-zero defaults), `research/experiments/registry.py`.
5. LLM: `finance_model/grounding.py` (`[evidence_id]` citation gate; fail-closed).
6. Portfolio/Risk: `RiskLimits` (qty/notional/position/exposure/leverage/tolerance/rate/TTL), `KillSwitch` (same-actor re-arm), `TradeIntent/RiskDecision`, `RiskFirewall.check` (kill→auth→dedupe→size→position→tolerance→staleness).
7. Execution: `ManagedOrder`, `OrderManagementSystem` (VALIDATED→RISK→SUBMITTED→ACK), `ExecutionReconciler.check_unknown_order`, simulator `BrokerInterface` conformance (connect/account/positions/orders/market/place/status) keeping legacy `submit_order` for tests.
8. Twin: existing `digital_twin/counterfactual` retained (deterministic; risk never bypassed).
9. Memory/Learning: existing attribution/gate/protected-failures retained.
10. Storage/Obs: `storage/repositories/catalog.py` (DuckDB+Parquet index design).
11. Native: Rust+C++ kept; parity policy documented (see §4).
12. Validation: `walk_forward/splitter.py`, `out_of_sample/evaluator.py` (Sharpe/MDD/trades), `regression/baseline.py` (protected gate).

## 3. Research integrated

- Risk: FIA automated-trading controls, Nasdaq EQRC (fat-finger, duplicative/message-rate, gross exposure watch/warn/action, safety switch), NYSE Pillar (price protection, kill switch semantics), Cboe CFE (pre-order vs post-execution), Euronext RiskGuard (suspend/block, MEP thresholds).
- Native: `pyrust-bt` (PyO3+maturin, DuckDB store), `raptorbt` (<1ms backtests, 33 metrics, Rayon, bit-determinism), `GlowBack` (event-driven + Arrow/Parquet + SQLite catalog), `AKQuant` (Rust event bus OrderRequest→Validated→ExecutionReport, polars zero-copy). Pattern adopted: Python shell, Rust hot loop, GIL released.
- LLM grounding: `FinGround` (atomic-claim taxonomy + formula re-compute ±0.5% + table-cell citations), `FAITH` (lookup vs comparative/bivariate/multivariate reasoning), `EvidenT` (inference-time citation+span traceability), `FINLFQA` (evidence+numeric+knowledge attribution). Adopted: cite-or-abstain gate in `grounding.py`.

## 4. C++/Rust + LLM plan (locked)

- Rust-first hot path via PyO3/maturin (`delta_native`), C++ for SIMD kernels via C ABI (`delta_checksum` today; extend to normalize/features/matching). Parity: same workload, `rel 1e-9/abs 1e-12`, benchmark metadata + commit hash. GPU only with proven parallelism.
- LLM: local/open models, prompt versioning, 8k context cap, tool allowlist, `FinancialAnalysis` structured output only; `verify_grounding` blocks uncited claims; no broker access; FIN-Bench 12 dims to be scored with rubrics in DOCX v1.1 appendix.

## 5. Remaining work (ordered)

1. DB wiring (DuckDB+Parquet + SQLite catalog migrations), corporate-action/calendar adjustments.
2. Full signal/factor library + calibrated forecasts (ECE/Brier) + constrained optimizer math.
3. Strategy harness wiring broker+risk+portfolio into backtest; TWAP/VWAP/POV/IS algos.
4. Local-LLM router + prompt registry + FIN-Bench dataset + calibration/abstention metrics.
5. Post-trade monitoring, VaR/CVaR, scenario/tail/liquidity risk, attribution.
6. Chaos/security/property/e2e suites + perf regression harness + release certification gate.
7. Rust kernels for normalize/feature/replay/risk/matching + `maturin` CI wheels + Criterion benches.

## 6. DOCX v1.1 changes

Added appendices: A schemas, B cost formulas, C risk numbers/TTLs/kill-switch SOP, D OMS/broker interface, E twin parameters, F LLM routing/grounding, G FFI boundary, H storage ER, I latency budgets, J FIN-Bench rubrics, K promotion gates, L CLI JSON. Core 12-block order and 8 invariants unchanged.
