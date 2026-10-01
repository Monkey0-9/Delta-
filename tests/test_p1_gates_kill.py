"""P1 tests: G1-G16 gate harness + kill-switch prod wiring."""
from __future__ import annotations

import sys

sys.path.insert(0, ".")


def test_gates_require_all_16_with_evidence():
    from finance_model.evaluation.delta_gates import GateId, GateStatus, evaluate_gates
    full = {g: (GateStatus.PASS, f"ev:{g.value}") for g in GateId}
    rep = evaluate_gates("m-test", full)
    assert rep.passed and rep.failed() == () and rep.blocking() == ()
    # One failure blocks promotion (no mean-score escape).
    bad = dict(full)
    bad[GateId.G6_FORECAST_CALIBRATION] = (GateStatus.FAIL, "ece=0.31")
    rep2 = evaluate_gates("m-test", bad)
    assert not rep2.passed and rep2.failed() == (GateId.G6_FORECAST_CALIBRATION,)
    # UNPROVEN is never PASS.
    unp = dict(full)
    unp[GateId.G7_RISK_REASONING] = (GateStatus.UNPROVEN, "unproven:needs_oracle_suite")
    rep3 = evaluate_gates("m-test", unp)
    assert not rep3.passed and rep3.unproven() == (GateId.G7_RISK_REASONING,)
    # Missing gate / empty evidence fail closed.
    missing = {g: (GateStatus.PASS, "e") for g in GateId if g != GateId.G1_FINANCIAL_KNOWLEDGE}
    assert not evaluate_gates("m", missing).passed
    empty = dict(full)
    empty[GateId.G4_GROUNDEDNESS] = (GateStatus.PASS, "")
    assert not evaluate_gates("m", empty).passed


def test_rule_probes_deterministic_and_honest():
    from finance_model.evaluation.delta_gates import GateId, GateStatus, run_rule_probes
    p1 = run_rule_probes()
    p2 = run_rule_probes()
    assert p1 == p2
    for g in (GateId.G2_NUMERICAL_CORRECTNESS, GateId.G5_TEMPORAL_CORRECTNESS,
              GateId.G10_HALLUCINATION_ABSTENTION, GateId.G14_REPRODUCIBILITY,
              GateId.G15_CONTAMINATION):
        status, ev = p1[g]
        assert status == GateStatus.PASS, (g, ev)
    # Honest capability probes: uncalibrated cost engine must FAIL, not pass.
    status, ev = p1[GateId.G12_TRADING_SIMULATION]
    assert status == GateStatus.FAIL and "calibrated=False" in ev, (status, ev)
    # No gate may claim capability without a real test: the rest are UNPROVEN.
    for g in (GateId.G1_FINANCIAL_KNOWLEDGE, GateId.G3_FINANCIAL_REASONING,
              GateId.G4_GROUNDEDNESS, GateId.G6_FORECAST_CALIBRATION,
              GateId.G7_RISK_REASONING, GateId.G8_PORTFOLIO_REASONING,
              GateId.G9_TOOL_USE_CORRECTNESS, GateId.G11_ADVERSARIAL_ROBUSTNESS,
              GateId.G13_LATENCY, GateId.G16_REGRESSION):
        status, ev = p1[g]
        assert status == GateStatus.UNPROVEN, (g, status, ev)
        assert ev.startswith("unproven:"), (g, ev)
    # Every gate runs with non-empty evidence; report does not pass while
    # anything is UNPROVEN or FAIL.
    from finance_model.evaluation.delta_gates import evaluate_gates
    for g in GateId:
        status, ev = p1[g]
        assert isinstance(ev, str) and ev, g
        assert "probe_not_implemented" not in ev, g
    rep = evaluate_gates("m", p1)
    assert not rep.passed and set(rep.blocking()) == set(GateId) - {
        GateId.G2_NUMERICAL_CORRECTNESS, GateId.G5_TEMPORAL_CORRECTNESS,
        GateId.G10_HALLUCINATION_ABSTENTION, GateId.G14_REPRODUCIBILITY,
        GateId.G15_CONTAMINATION}


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
