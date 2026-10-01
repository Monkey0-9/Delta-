# P2 Institutional Build — Evidence Ledger (2026-10-01)

Parallel workstreams launched. Status per S55 labels (Implemented / Partially validated / Not implemented / Unknown).

## Stream A — Truth & Integration: Partially validated
- `core/domain/canonical.py` NEW: SevenTimestamps (event<=publication<=availability<=ingestion enforced),
  Canonical* x14, Maturity/ResearchGrade/ModelStatus. Time-travel rejected, PIT `is_usable_at` tested.
- `data/market/exchange_calendar.py`: +`next_open/next_close/is_auction/is_halted`, venue fail-closed (CME raises),
  `_utc` helper. Covers §8 `is_open/next_open/next_close/session/is_holiday/is_early_close/is_auction/is_halted`.
- `delta_tui/screens/core.py` + `ops.py`: purged illustrative SPX/NASDAQ/VIX, 177.42 quote, 1800/1200 sizes,
  $1M portfolio, VaR99 2.14, 812k eps, VWAP 12400/25000, scenario/model lists. Now live-or-UNAVAILABLE/DEGRADED
  with zero fallbacks. Rust `tui/src/app.rs:321` canned values remain — tracked gap, Python TUI is primary.
- Cost engine labeled `calibrated=False, calibration_id=proxy-uncalibrated` — cannot pass R5 until fill-calibrated.

## Stream B — Quant: Implemented (not yet certified)
- `research/alpha_contract.py` NEW: ONE AlphaContract/Registry/Metadata, `promote()` requires dataset_hash for
  VALIDATED+, `rank_ic` deterministic helper. Legacy G1/G2 factories to delegate (pending).
- Optimizer family (8 methods), 20-factor library, VaR-historical, stress-engine exist — hardening/capacity/DSR-PBO
  wiring is next.

## Stream C — Execution: Partially validated
- OMS state machine + gateway + live-engine evidence gates + paper lifecycle + reconcile exist.
- Calibration gap explicitly labeled; L2/L3 replay + queue + TCA wiring next.

## Stream D — AI/Agents: Implemented (competence unproven)
- `agent/runtime/budgets.py` NEW: per-role budgets + BudgetTracker + compensating-action rollback (no DB-undo).
  Wired into `AgentRuntime.execute()` deny-on-exhaust.
- `data/news/trust.py` NEW: NewsItem with hash, quarantine on injection pattern
  (`IGNORE ALL PRIOR...BUY 1M` stays text), `is_trusted_for_tools()`.
- Finance G-gates still 5/16 real — FinBench + calibration + tool-use next.

## Tests
- `tests/test_p2_institutional.py` NEW: 7 tests green.
- Regression: p0_safety + p1_gates_kill + p1_paper_lifecycle + p2 = 20 passed.

## Explicitly NOT claimed
BlackRock/JPMC/Goldman parity, live trading, production FIX, IBKR, full L2/L3 replay, calibrated impact,
finance-model competence, external observability exporter. See `docs/STUB_AUDIT.md` 5 PRODUCTION-GAPs (unchanged).
