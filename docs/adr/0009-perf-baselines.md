# ADR 0009 — Performance requirements: approved baselines (Q-gate)

- Version: 1.0 / Date: 2026-10-11 / Status: accepted
- Context: the P0 plan set aspirational targets (firewall <7µs/check, native
  LOB 10M ops/s) that no measured run has met. The Q completion gate requires
  *approved* requirements on documented hardware — an unmet aspiration is
  not a requirement, and silently editing targets is forbidden.
- Decision:
  1. PAPER/RESEARCH requirement = measured baseline + regression guard.
     Approved baselines (this class of box, 20-core Linux/Py3.13, bench
     artifact 2026-10-11):
     - risk firewall check: p50 ~97µs / p99 ~193µs
     - OMS journal append (fsync): p50 ~448µs
     - gateway submit (paper-routed): p50 ~23µs
     - native LOB: ~233k ops/s
     SRE rules guard ~2x (warning) / ~4x (critical) of the firewall p99.
  2. The P0 aspirational targets (7µs, 10M ops/s) remain recorded bench
     FAILs and become LIVE-gate requirements satisfiable ONLY on isolated,
     documented hardware with a fresh bench artifact — never by editing
     thresholds to fit shared-box numbers.
  3. Optimization work must never bypass risk, audit, or validation (the
     fsync-per-append cost above is the price of RPO=0; removing it needs
     its own ADR with a revised crash contract).
- Consequences: bench_certify.py keeps aspirational targets as FAIL verdicts;
  ops_rules.py thresholds track 2x/4x of the approved baseline; any future
  re-baselining cites a new bench artifact hash + date.
