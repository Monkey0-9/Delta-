# ADR 0004 — PIT temporal integrity + experiment provenance (Groups 12/30)

- Status: accepted / Date: 2026-10-02 / Version: 1.0
- Chain: `t_event <= t_published <= t_available <= t_decision <= t_execution`
  enforced by `data/pit/gate.py::check_chain` (+ `data/pit/leakage.py` guards).
- Datasets are snapshotted with SHA manifests; train/validation/OOS enforced.
- Experiments persist in SQLite (`research/ledger/sqlite_registry.py`) with
  immutable manifests; `reproduce(EXP-ID)` verifies the manifest hash.
- Provenance per experiment: EXP-ID, CODE SHA, DATASET SHA, FEATURE/MODEL/
  PARAMETER VERSION, ENVIRONMENT, SEED, PERIODS, COST/EXECUTION/PORTFOLIO/
  RISK models, RESULT HASH.
