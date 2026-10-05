# ADR 0005 — Latency methodology + R0..R10 certification ladder (Groups 17/30)

- Status: accepted / Date: 2026-10-02 / Version: 1.0
- Latency reports `simulated_latency_ms` (modelled market) separately from
  `compute_ms` (DELTA overhead); SLA graphs use the modelled series
  (`simulation/market_simulator/latency_model.py`, `execution/realism.py`).
- No perf claims without measured p50/p95/p99/p99.9/p99.99 on documented hardware.
- Ladder: R0 Research, R1 Reproducible, R2 Statistical, R3 OOS, R4 Stress,
  R5 Capacity, R6 Execution, R7 Paper, R8 Shadow, R9 Candidate, R10 Production.
- No R10 without all prior gates green + sign-offs
  (`execution/oms_unify.py::certify`, `research/gates.py`).
- Production change freeze + rollback plan required post-R10.
