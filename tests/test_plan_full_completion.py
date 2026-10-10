"""Full plan completion: VNEXT Groups 01-30 + P0-cert Sprints + legacy plans.

One test per group family; deterministic; no fake live data.
"""
from core.plan_completion import (
    ALPHA_FAMILIES,
    OMS_STATES,
    R_GATES,
    SHOCKS,
    VALID_MODES,
    adjust_split,
    almgren_chriss,
    bad_tick,
    black_litterman,
    branch_compare,
    breach_watch,
    calibrated_gate,
    capacity_curve,
    certify_ladder,
    classify_regime_full,
    compounding_pbo_proxy,
    concentration_report,
    deflated_sharpe,
    diagnose_failure,
    ensemble_combine,
    expected_shortfall,
    fix_lifecycle,
    gate_signoff,
    half_life,
    ibkr_contract,
    information_coefficient,
    journal_replay,
    lake_path,
    mandate_hash_fn,
    max_diversification,
    mean_variance,
    neutralize,
    new_session_id,
    oms_transition,
    parse_intent,
    participation_cost,
    pit_join,
    pit_universe,
    purge_embargo_split,
    quarantine,
    rank_opportunities,
    reference_release,
    register_feature,
    register_model,
    reverse_stress_threshold,
    risk_parity,
    scenario_replay,
    session_diff,
    shadow_soak_ok,
    sor_expected_shortfall,
    sqrt_impact,
    sre_alerts,
    tail,
    tca_loop,
    transition_matrix,
    tri_tier_source,
    twap_schedule,
    value_at_risk,
    vwap_schedule,
    what_if,
)


def test_g01_arch_rules():
    from core.architecture import OWNERS, check_import
    assert set(OWNERS) >= {"data", "alpha", "risk", "execution", "research"}
    assert not check_import("risk/x.py", "delta_tui/app.py")
    assert check_import("delta_tui/app.py", "config/mode.py")


def test_g02_hygiene_guards():
    import pathlib
    repo_root = pathlib.Path(__file__).resolve().parents[1]
    assert (repo_root / ".gitignore").exists()
    assert (repo_root / "docs/adr/0002-bounded-contexts.md").exists()


def test_g03_profiles_hashing():
    from config.profiles import load_profile, research_block, simulation_block
    for p in ("paper", "shadow", "simulation", "research"):
        cfg = load_profile(p)
        assert cfg["_sha"] and len(cfg["_sha"]) == 64
    assert research_block(7)["embargo_bars"] == 5
    assert simulation_block()["venue"] == "SIM"
    try:
        load_profile("nope")
        assert False
    except ValueError:
        pass


def test_g04_session_event_permission():
    from delta_tui.security.permissions import check
    assert check("kill", confirmed=False).needs_confirm
    assert check("kill", confirmed=True).allowed
    assert new_session_id().startswith("sess-")
    assert mandate_hash_fn({"a": 1}) == mandate_hash_fn({"a": 1})
    d = session_diff({"mandate_hash": "x", "mode": "PAPER"},
                     {"mandate_hash": "y", "mode": "PAPER"})
    assert d["mandate_drift"] and d["mode_same"]
    assert set(VALID_MODES) == {"LIVE", "PAPER", "SIMULATION", "RESEARCH", "DEMO"}


def test_g0506_modal_toast_a11y():
    from delta_tui.a11y import plain_text, to_ascii_safe
    from delta_tui.widgets.modal import ModalManager
    from delta_tui.widgets.toast import ToastManager
    mm = ModalManager()
    mm.confirm_kill()
    assert mm.resolve("CONFIRM") and mm.current() is None
    tm = ToastManager()
    tm.breach("b")
    assert len(tm.items()) == 1
    assert to_ascii_safe("hi") == "hi"
    assert "risk" in plain_text("risk", "gross").lower()


def test_g07_deeplink():
    from delta_tui.navigation.deeplink import alpha_lineage
    assert "momentum" in alpha_lineage("momentum-v4", None)


def test_g08_responsive():
    from delta_tui.responsive_probe import display_probe, layout_for_width, on_resize
    assert layout_for_width(160) == "full"
    assert layout_for_width(80) == "collapsed"
    assert on_resize(100, 30)["layout"] == "narrow"
    assert display_probe()["width"] > 0


def test_g09_full_command_ux():
    from delta_tui.commands.aliases import nl_parity, parse_book_args
    from delta_tui.commands.registry import lookup
    from delta_tui.commands.ux import dispatch, fuzzy_rank, unknown_guidance
    for cmd in ("book", "analyze", "scenario", "alpha", "portfolio",
                "risk", "execution", "system", "stress", "attribution",
                "optimize", "inspect", "compare", "kill"):
        assert lookup(cmd) is not None, cmd
    assert parse_book_args("/book NVDA --depth 5") == {"symbol": "NVDA", "depth": 5}
    assert "Did you mean" in unknown_guidance("bok")
    assert "book" in fuzzy_rank("bok")
    assert "CONFIRM" in dispatch("/kill", confirmed=False)
    assert nl_parity("kill everything now", "/kill")


def test_g11_market():
    assert tri_tier_source(True, False) == "SOURCE/live"
    assert tri_tier_source(False, False).endswith("DEMO")
    assert bad_tick(-1, 100) and bad_tick(150, 100)
    assert not bad_tick(101, 100)


def test_g12_pit():
    rows = [{"t_available": 1}, {"t_available": 9}]
    assert pit_join(rows, 5) == [{"t_available": 1}]
    members = [{"symbol": "A", "listed_at": 0, "delisted_at": 10},
               {"symbol": "B", "listed_at": 6, "delisted_at": 99}]
    assert pit_universe(members, 5) == ["A"]
    splits = purge_embargo_split(100, 2, 1, 1)
    assert len(splits) == 2 and splits[0][1][0] > splits[0][0][-1]


def test_g131415_lake_quality_ref():
    assert lake_path("raw", "NVDA", "2024-01-01").endswith(".parquet")
    good, bad = quarantine([{"bad": True}, {"bad": False}], lambda r: r["bad"])
    assert len(good) == 1 and len(bad) == 1
    assert len(reference_release({"v": 1})) == 16
    assert adjust_split([100.0], 2.0) == [50.0]


def test_g1617_micro_latency():
    from core.plan_completion import LatencySample, QueueState
    q = QueueState(ahead_qty=90, position=9)
    assert 0 < q.fill_prob(10) < 1.0
    s = LatencySample(0.2, 0.1, 0.01, 0.5)
    assert abs(s.simulated_ms - 0.81) < 1e-9
    assert tail([1, 2, 3, 4], 0.99) == 4


def test_g18_costs():
    assert sqrt_impact(100, 10000, 0.02) > 0
    ac = almgren_chriss(100, 10000, 0.02)
    assert ac["total"] == ac["temporary"] + ac["permanent"]
    assert participation_cost(0.5) > participation_cost(0.1)


def test_g19_scenarios():
    assert len(SHOCKS) == 10
    r = scenario_replay("2008", 100.0)
    assert r["stressed"] < 100.0 and "costs" in r["attribution"]
    assert reverse_stress_threshold(100.0, 10.0) > 0


def test_g2021_alpha():
    assert len(ALPHA_FAMILIES) == 10
    res = neutralize([1.0, 2.0, 3.0], [1.0, 1.0, 1.0])
    assert len(res) == 3
    assert half_life([0.1, 0.05, 0.02]) >= 1
    assert ensemble_combine({"a": 1.0, "b": 2.0}) > 0


def test_g22_validation():
    ic = information_coefficient([1, 2, 3, 4], [1, 2, 3, 4])
    assert abs(ic - 1.0) < 1e-9
    assert deflated_sharpe(2.0, 100) < 2.0
    assert compounding_pbo_proxy([1, 1], [-1, 1]) == 0.5


def test_g23_capacity():
    curve = capacity_curve(100.0, 10_000_000)
    assert len(curve) == 7 and curve[-1]["net_bps"] < curve[0]["net_bps"]


def test_g24_world():
    assert classify_regime_full(0.5, 0.8)["regime"] == "stress"
    assert classify_regime_full(0.1, 0.2, 0.9)["regime"] == "calm"
    m = transition_matrix({("calm", "calm"): 8, ("calm", "stress"): 2})
    assert abs(m["calm"]["calm"] - 0.8) < 1e-9


def test_g25_ml_registry():
    h = register_feature("mom_20", "v2")
    assert h
    register_model("m-cal", h, True)
    try:
        register_model("m-bad", h, False)
        assert False
    except ValueError:
        pass
    assert calibrated_gate(0.03) and not calibrated_gate(0.2)


def test_g26_portfolio():
    assert sum(mean_variance([0.1, 0.2])) <= 0.4 + 1e-9
    assert len(risk_parity([0.1, 0.2])) == 2
    assert black_litterman([0.1], [0.3])[0] > 0.1
    assert len(max_diversification([0.1, 0.2])) == 2


def test_g27_risk():
    rets = [-0.01 * i for i in range(1, 101)]
    assert value_at_risk(rets) >= 0
    assert expected_shortfall(rets) >= value_at_risk(rets)
    assert breach_watch(5.0, 0.2, 0.5) == ["gross", "var99", "concentration"]
    assert breach_watch(1.0, 0.01, 0.05) == []


def test_g28_oms_sor_fix():
    assert set(OMS_STATES) >= {"CREATED", "FILLED", "REJECTED"}
    assert oms_transition("CREATED", "validate") == "VALIDATED"
    try:
        oms_transition("CREATED", "fill")
        assert False
    except ValueError:
        pass
    venues = [{"venue": "A", "spread_bps": 9, "fee_bps": 1},
              {"venue": "B", "spread_bps": 2, "fee_bps": 1}]
    assert sor_expected_shortfall(venues) == "B"
    assert "PAPER-ONLY" in ibkr_contract("AAPL")["status"]
    assert tca_loop(7, 9)["err_bps"] == 2


def test_g29_agent():
    assert "PIT" in diagnose_failure("data")
    assert branch_compare({"net_sharpe": 1}, {"net_sharpe": 2}) == "B"


def test_g30_r_gates_prod():
    assert certify_ladder({g: True for g in R_GATES}) == "R10"
    assert certify_ladder({"R0": True}) == "R1"


def test_p0cert_sprints():
    assert "Logon(A)" in " ".join(fix_lifecycle())
    assert journal_replay([{"event": "validate"}, {"event": "risk_ok"}])["final"] == "RISK_APPROVED"
    assert sre_alerts()["kill_switch_state"] == "ARMED"
    assert gate_signoff({"quant": True, "engineering": True, "risk": True,
                         "infosec": True, "operations": True})
    assert not gate_signoff({"quant": True})
    assert shadow_soak_ok(14, 0.0) and not shadow_soak_ok(3, 0.0)


def test_legacy_trader_decision():
    assert parse_intent("what should I trade today?") == "FIND_TRADES_TODAY"
    assert parse_intent("stress my portfolio") == "STRESS_TEST_PORTFOLIO"
    opps = rank_opportunities([{"sharpe": 1}, {"sharpe": 2}])
    assert opps[0]["sharpe"] == 2
    assert concentration_report({"A": 0.9})["alert"]
    assert what_if({"A": 0.5}, {"symbol": "B", "delta": 0.1})["gross"] > 0
    assert sum(twap_schedule(100, 4)) == 100
    assert abs(sum(vwap_schedule(100, [1, 1])) - 100) < 1e-9
