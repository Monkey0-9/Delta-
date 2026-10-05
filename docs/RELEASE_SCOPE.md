# DELTA RELEASE SCOPE (formal board)

- Version: 1.0 / Date: 2026-10-01 / Status: active
- Release: DELTA-PAPER-LAUNCH

## P0 GO-LIVE BLOCKERS (must be PASS for PAPER launch)
- RScope-01 Owner:eng Status:done AC: single TUI entry, typed viewmodels Evidence:tests/test_vnext_p0.py 7/7
- RScope-02 Owner:eng Status:done AC: kill bypasses LLM, needs CONFIRM Evidence:tests/test_vnext_p0_remainder.py
- RScope-03 Owner:quant Status:done AC: PIT no-leakage battery Evidence:tests/test_p1_pit_adversarial.py
- RScope-04 Owner:eng Status:done AC: paper gateway->fill->reconcile Evidence:tests/test_p1_paper_lifecycle.py
- RScope-05 Owner:risk Status:done AC: risk evidence gate + kill board Evidence:tests/test_p1_gates_kill.py

## P1 REQUIRED (PAPER launch, LIVE gated)
- RScope-06 Owner:quant Status:partial AC: canonical market/PIT/micro replay Evidence:tests/test_vnext_launch.py
- RScope-07 Owner:sec Status:open AC: independent SAST/DAST/pentest sign-off Evidence: NONE -> LIVE blocker
- RScope-08 Owner:ops Status:open AC: 10min/1h soak + rollback rehearsal Evidence: NONE -> LIVE blocker
- RScope-09 Owner:ops Status:open AC: prod monitoring/on-call + /healthz Evidence: PARTIAL (module exists, no prod wiring)
- RScope-10 Owner:stake Status:open AC: signed UAT + Go/No-Go minutes Evidence: NONE -> LIVE blocker

## P2 POST-LAUNCH
- Weeks-long paper/shadow evidence, TCA calibration, scenario regression.

## P3 FUTURE RESEARCH
- HMM world, full 10-family calibrated alphas, native perf at scale.
