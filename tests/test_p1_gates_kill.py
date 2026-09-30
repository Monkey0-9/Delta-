"""P1 tests: G1-G16 gate harness + kill-switch prod wiring."""
from __future__ import annotations

import sys

sys.path.insert(0, ".")


def test_gates_require_all_16_with_evidence():
    from finance_model.evaluation.delta_gates import GateId, evaluate_gates
    full = {g: (True, f"ev:{g.value}") for g in GateId}
    rep = evaluate_gates("m-test", full)
    assert rep.passed and rep.failed() == ()
    # One failure blocks promotion (no mean-score escape).
    bad = dict(full)
    bad[GateId.G6_FORECAST_CALIBRATION] = (False, "ece=0.31")
    rep2 = evaluate_gates("m-test", bad)
    assert not rep2.passed and rep2.failed() == (GateId.G6_FORECAST_CALIBRATION,)
    # Missing gate / empty evidence fail closed.
    missing = {g: (True, "e") for g in GateId if g != GateId.G1_FINANCIAL_KNOWLEDGE}
    assert not evaluate_gates("m", missing).passed
    empty = dict(full)
    empty[GateId.G4_GROUNDEDNESS] = (True, "")
    assert not evaluate_gates("m", empty).passed


def test_rule_probes_deterministic_and_honest():
    from finance_model.evaluation.delta_gates import GateId, run_rule_probes
    p1 = run_rule_probes()
    p2 = run_rule_probes()
    assert p1 == p2
    for g in (GateId.G2_NUMERICAL_CORRECTNESS, GateId.G5_TEMPORAL_CORRECTNESS,
              GateId.G10_HALLUCINATION_ABSTENTION, GateId.G14_REPRODUCIBILITY,
              GateId.G15_CONTAMINATION):
        ok, ev = p1[g]
        assert ok, (g, ev)
    # Unimplemented gates must say so, never silently pass.
    ok, ev = p1[GateId.G12_TRADING_SIMULATION]
    assert not ok and ev.startswith("probe_not_implemented")


def test_kill_wiring_runs_both_halts_and_binds_board():
    from risk.emergency.breaker import CircuitBreaker
    from risk.kill_switch.kill_switch import KillSwitchBoard
    from risk.kill_switch.wiring import wire_kill
    board, br = KillSwitchBoard(), CircuitBreaker()
    calls: list[str] = []
    w = wire_kill(board, br, oms_cancel=lambda: calls.append("oms"),
                  engine_halt=lambda: calls.append("engine"))
    assert w.board is board
    br.trigger("p1-test")
    assert calls == ["oms", "engine"]
    assert board.any_active()
    # Refuse decorative wiring.
    try:
        wire_kill(board, CircuitBreaker(), oms_cancel=None, engine_halt=lambda: None)  # type: ignore[arg-type]
        assert False, "must raise"
    except ValueError:
        pass
