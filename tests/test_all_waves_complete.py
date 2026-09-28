"""All-waves completion gate: W001-W250 launch slice in one fast test module."""
from __future__ import annotations

from decimal import Decimal


def test_architecture_adr_and_config_profiles():
    from pathlib import Path
    assert Path("docs/ADR-001-architecture.md").exists()
    from config.loader import load_config, config_hash, snapshot_config
    for env in ("research", "simulation", "paper", "shadow", "prod"):
        cfg = load_config(env)
        assert cfg["env"] == env and cfg["execution"]["live_trading"] is False
    snap = snapshot_config("paper")
    assert len(snap["config_hash"]) == 64
    try:
        load_config("live")
        raise AssertionError("unknown env allowed")
    except ValueError:
        pass


def test_alpha_families_and_validation_pipeline():
    from quant.alpha.families import FAMILIES, get, validation_pipeline
    assert len(FAMILIES) == 10
    assert get("momentum").implemented is True
    assert "deflated_sharpe" in validation_pipeline() and "pbo" in validation_pipeline()
    import delta_compat  # noqa
    from research.real_loop import alpha_stats
    assert callable(alpha_stats.deflated_sharpe) and callable(alpha_stats.combinatorial_pbo)
    assert callable(alpha_stats.benjamini_hochberg) and callable(alpha_stats.newey_west_t)


def test_venue_routing_and_fix_session():
    from execution.routing import best_venue, score_venue, PAPER_VENUES, route_order
    v = best_venue(Decimal("100"))
    assert v in PAPER_VENUES and score_venue(v, Decimal("100")) >= 0
    r = route_order(quantity=Decimal("100"), adv=Decimal("1000000"))
    assert r.slices == 1 and r.venue == "paper-venue"
    try:
        route_order(quantity=Decimal("100"), adv=Decimal("1000000"), mode="live")
        raise AssertionError("live routing allowed")
    except ValueError:
        pass
    from execution.fix.governed import GovernedSession
    s = GovernedSession("DELTA", "PAPER-VENUE", mode="paper")
    assert s.logon() is True and s.heartbeat() >= 1
    assert s.send_new_order([("11", "o1"), ("55", "SPY")])
    try:
        GovernedSession("DELTA", "LIVE", mode="live")
        raise AssertionError("live FIX allowed")
    except ValueError:
        pass


def test_oms_agent_shadow_present():
    from execution.oms.state_machine import OrderState
    assert OrderState.CREATED.value == "CREATED" and OrderState.FILLED.value == "FILLED"
    from agent.tools.registry import ToolRegistry
    reg = ToolRegistry()
    reg.register(name="backtest", description="run backtest",
                 function=lambda: {"ok": True}, permissions=frozenset())
    assert reg.get("backtest").name == "backtest"
    from deployment.shadow import ShadowRunner, ShadowDecision
    runner = ShadowRunner()
    runner.record(ShadowDecision("c1", "BUY", 10.0, "BUY", 5.0))
    assert runner.evaluate("c1") is not None


def test_parallel_scheduler_and_slo_gates():
    from research.experiments.scheduler import run_parallel
    out = run_parallel(("E1", "E2", "E3"), base_seed=7,
                       worker=lambda eid, seed: f"{eid}@{seed}")
    assert [r.experiment_id for r in out] == ["E1", "E2", "E3"]
    assert [r.seed for r in out] == [7, 8, 9]
    assert all(r.status == "PASS" for r in out)
    try:
        run_parallel(("BAD",), base_seed=1,
                     worker=lambda eid, seed: (_ for _ in ()).throw(ValueError("boom")))
        raise AssertionError("fabric swallowed failure")
    except RuntimeError:
        pass
    from observability.slos import check_latency_slo, check_error_budget
    assert check_latency_slo((4.0, 5.0, 6.0, 8.0), 10.0, 20.0, 50.0).status == "PASS"
    assert check_latency_slo((), 10.0, 20.0, 50.0).status == "FAIL"  # no data = FAIL
    assert check_error_budget(0, 10000).status == "PASS"
    assert check_error_budget(5, 10000).status == "FAIL"  # 0.0005 > 0.0001 budget


def test_capacity_curve_real_math():
    from research.capacity.curve import capacity_curve, max_capacity
    curve = capacity_curve(15.0, adv_shares=1_000_000.0, price=500.0)
    assert [p.capital for p in curve] == [1e6, 10e6, 50e6, 100e6]
    costs = [p.total_cost_bps for p in curve]
    assert costs == sorted(costs)  # cost grows with capital
    assert curve[0].total_cost_bps < 15.0 < curve[-1].total_cost_bps
    assert max_capacity(15.0, adv_shares=1_000_000.0, price=500.0) == 1e6
    import pytest
    with pytest.raises(ValueError):
        capacity_curve(0.0, adv_shares=1_000_000.0, price=500.0)
