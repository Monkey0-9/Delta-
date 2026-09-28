"""W151-W250: institutional verification program tests.

Historical reality -> microstructure -> execution -> autonomous research ->
provenance/model lifecycle -> reliability/evidence. Research truth +
execution truth -> production truth -> live evidence.
"""
from decimal import Decimal

# ---- maturity wording ----
from validation.maturity import (
    DOMAIN_POSITION,
    PLATFORM_STATEMENT,
    current_boundary,
    report,
)


def test_maturity_honest_statement():
    assert "live institutional production remains gated" in PLATFORM_STATEMENT
    assert "Ready for Institutional Production" not in PLATFORM_STATEMENT
    assert "DELTA-3" in current_boundary()
    r = report()
    assert "Institutional live data" in r and "MISSING" in r
    assert "Evidence of actual alpha" in r and "NOT established" in r
    assert len(DOMAIN_POSITION) >= 15


# ---- A. feed abstraction (W151-170) ----
from data.feed_abstraction import (
    MultiAssetDataset,
    SyntheticVendor,
    reconcile_vendors,
)


def test_feed_canonical_schema_vendor_agnostic():
    a = SyntheticVendor("Yahoo", seed=7)
    b = SyntheticVendor("Polygon", seed=8)
    ba = a.fetch_bars("AAA", 0, 120_000_000_000)
    bb = b.fetch_bars("AAA", 0, 120_000_000_000)
    assert ba and bb and ba[0].vendor == "Yahoo"
    assert ba[0].__dataclass_fields__.keys() == bb[0].__dataclass_fields__.keys()


def test_vendor_reconciliation_quantifies_disagreement():
    a = SyntheticVendor("Yahoo", seed=7).fetch_bars("AAA", 0, 60_000_000_000)
    b = SyntheticVendor("Polygon", seed=8).fetch_bars("AAA", 0, 60_000_000_000)
    rep = reconcile_vendors("AAA", {"Yahoo": a, "Polygon": b})
    assert len(rep) == len(a) == len(b)
    assert all(d.max_price_rel >= 0 and d.volume_rel_gap >= 0 for d in rep)
    # missing vendor surfaced, never hidden
    rep2 = reconcile_vendors("AAA", {"Yahoo": a, "Polygon": b[:1]})
    assert any(d.missing_in for d in rep2)


def test_multi_asset_pit_scale():
    ds = MultiAssetDataset()
    for ac, sym in [("equity", "AAA"), ("future", "ES"), ("fx", "EURUSD"),
                    ("crypto", "BTC"), ("commodity", "GC"), ("rate", "TNX"),
                    ("etf", "SPY")]:
        ds.add(SyntheticVendor("syn", seed=3, asset_class=ac).fetch_bars(sym, 0, 60_000_000_000))
    assert set(ds.asset_classes()) == {"commodity", "crypto", "equity", "etf", "future", "fx", "rate"}
    assert len(ds.asof("AAA", 60_000_000_000)) == 2
    assert ds.asof("AAA", 0)[0].ts_ns == 0
    assert ds.content_hash("AAA", "syn") == ds.content_hash("AAA", "syn")


# ---- B+C. microstructure + execution (W171-190) ----
from simulation.exchange_replay import (
    EmpiricalLatency,
    ExchangeReplayer,
    OrderLifecycle,
    QueueCalibrationTable,
    VenueStats,
    expected_venue_cost_bps,
    route_empirical,
)
from simulation.l3_engine import L3Book, L3Event


def test_exchange_replay_tape_to_fill():
    book = L3Book()
    # market offers resting liquidity first
    book.apply(L3Event(1, 1, "ADD", "m1", "sell", Decimal("10"), Decimal("5")))
    book.apply(L3Event(2, 2, "ADD", "m2", "sell", Decimal("10"), Decimal("5")))
    rp = ExchangeReplayer(book)
    mine = L3Event(3, 3, "MARKET", "mine1", "buy", Decimal("0"), Decimal("6"))
    out = rp.run([], mine)
    assert out.filled == 6.0 and out.avg_px == 10.0


def test_exchange_replay_resting_queue_interaction():
    rp = ExchangeReplayer()
    mine = L3Event(1, 1, "ADD", "mine1", "buy", Decimal("9.9"), Decimal("5"))
    tape = [L3Event(2, 2, "MARKET", "t1", "sell", Decimal("0"), Decimal("2"))]
    out = rp.run(tape, mine)
    assert out.filled == 2.0  # lifted from my resting bid


def test_queue_calibration_prior_and_learning():
    t = QueueCalibrationTable()
    assert t.p_fill(queue_pos=0, spread_bps=1, imbalance=0.0, volatility=0.01) == 0.5
    for _ in range(8):
        t.observe(queue_pos=0, spread_bps=1, imbalance=0.0, volatility=0.01, filled=True)
    for _ in range(2):
        t.observe(queue_pos=0, spread_bps=1, imbalance=0.0, volatility=0.01, filled=False)
    assert t.p_fill(queue_pos=0, spread_bps=1, imbalance=0.0, volatility=0.01) == 0.8


def test_empirical_latency_stages():
    lat = EmpiricalLatency()
    for st, v in [("market_data", 100), ("network", 200), ("strategy", 300),
                  ("risk", 50), ("order_gateway", 150), ("exchange", 400)]:
        lat.add(st, v)
        lat.add(st, v * 2)
    assert lat.quantile("network", 0.5) == 200
    assert lat.total_quantile(0.5) == 1200
    try:
        lat.add("telepathy", 1)
        assert False
    except ValueError:
        pass


def test_order_lifecycle_full_and_cancel_paths():
    o = OrderLifecycle("o1")
    assert o.transition("ACK") and o.transition("PARTIAL", qty=4, px=10.0)
    assert o.transition("PARTIAL", qty=3, px=10.1) and o.transition("FILLED", qty=3, px=10.1)
    assert o.filled_qty == 10.0 and o.transition("CANCEL_REQ") is False  # terminal
    c = OrderLifecycle("o2")
    assert c.transition("ACK") and c.transition("CANCEL_REQ") and c.transition("CANCELLED")
    # duplicates idempotent, illegal rejected
    assert c.transition("CANCELLED", duplicate=True) is True
    r = OrderLifecycle("o3")
    assert r.transition("REJECTED") is True
    t = OrderLifecycle("o4")
    assert t.transition("TIMEOUT") and t.transition("DISCONNECTED") and t.transition("ACK")


def test_sor_empirical_beats_naive_quote_compare():
    venues = [VenueStats("A", 0.5, 0.2, 1.0, 50_000, 0.001, 0.6),
              VenueStats("B", 2.0, 0.0, 3.0, 500_000, 0.05, 0.1)]
    alloc = route_empirical(100.0, venues, adv=10_000.0)
    assert alloc[0][0] == "A"  # fee+latency+fail-aware, not just depth
    assert abs(sum(q for _, q in alloc) - 100.0) < 1e-6
    assert expected_venue_cost_bps(venues[1], qty=100, adv=10_000, adverse_bps=1.0) > \
        expected_venue_cost_bps(venues[0], qty=100, adv=10_000, adverse_bps=1.0)


# ---- D. alpha lab (W191-210) ----
from research.alpha_lab import (
    AlphaRecord,
    DecayLab,
    capacity_ladder,
    economic_limit,
    mutual_info_hist,
    orthogonalize,
    pairwise_corr,
)


def test_alpha_record_immutable_id():
    a = AlphaRecord.create("mom", 471, hypothesis="h", math_def="m",
                           universe=("AAA",), features=("f1",),
                           neutralization="sector", signal="s", holding_period_bars=5)
    assert a.alpha_id == "ALPHA-MOM-00471" and len(a.record_hash) == 12


def test_orthogonalization_removes_overlap():
    sig = {"m1": [1.0, 2.0, 3.0, 4.0], "m2": [2.0, 4.0, 6.0, 8.0]}
    assert pairwise_corr(sig["m1"], sig["m2"]) > 0.99
    assert mutual_info_hist(sig["m1"], sig["m2"]) > 0
    orth = orthogonalize(sig)
    assert abs(pairwise_corr(orth["m1"], orth["m2"])) < 0.2


def test_decay_lab_half_life():
    lab = DecayLab()
    d = lab.decay_curve([0.10, 0.08, 0.05, 0.03, 0.01, 0.005, 0.001])
    assert d["half_life_bars"] > 0 and len(d["curve"]) == 7


def test_capacity_ladder_answers_scale_question():
    pts = capacity_ladder(30.0, 50_000_000.0)
    assert len(pts) == 7 and pts[0].capital == 10_000
    assert pts[0].net_bps >= pts[-1].net_bps  # decay with scale
    lim = economic_limit(pts)
    assert lim > 0


# ---- E. hierarchical state ----
from world_model.hierarchical_state import HierarchicalState


def test_hierarchical_state_predict_update():
    hs = HierarchicalState.uniform()
    assert abs(sum(hs.levels["macro"].probs) - 1.0) < 1e-9
    pred = hs.levels["volatility"].predict(3)
    assert abs(sum(pred) - 1.0) < 1e-9
    hs.levels["macro"].update([0.1, 0.1, 0.4, 0.4])
    assert hs.levels["macro"].probs[3] > 0.25
    assert 0.0 <= hs.joint_stress_prob() <= 1.0
    assert hs.entropy() > 0


# ---- F. factor optimizer ----
from portfolio.factor_optimizer import (
    FACTORS,
    NonlinearCosts,
    factor_exposure,
    objective,
    optimize_factor_constrained,
)


def test_nonlinear_objective_penalizes_concentration():
    cov = [[0.04, 0.0], [0.0, 0.04]]
    c = NonlinearCosts()
    assert objective([0.5, 0.5], [0.1, 0.1], cov, [1.0, 1.0], c) > \
        objective([1.0, 0.0], [0.1, 0.1], cov, [1.0, 1.0], c)


def test_factor_caps_respected():
    cov = [[0.04, 0.01], [0.01, 0.09]]
    w = optimize_factor_constrained([0.15, 0.05], cov, {"beta": [1.0, 1.0]},
                                    {"beta": 0.2}, [1.0, 1.0], NonlinearCosts(),
                                    max_name=0.5, max_gross=1.0)
    assert abs(sum(w)) <= 0.2 + 1e-6
    assert len(FACTORS) == 11
    assert abs(factor_exposure(w, {"beta": [1.0, 1.0]})["beta"]) <= 0.2 + 1e-6


# ---- G. intraday risk + reverse stress ----
from risk.intraday_engine import IntradayRiskEngine, reverse_stress, var_es


def test_intraday_engine_snapshot():
    eng = IntradayRiskEngine(peak_nav=100.0)
    s = eng.update(positions=[10.0, -5.0], prices=[10.0, 20.0],
                   factor_loadings=[[1.0, 1.0]], pnl_history=[1.0, -0.5, 0.3, -2.0],
                   adv_frac=[0.5, 0.5], margin_used=0.3,
                   corrs=[[1.0, 0.4], [0.4, 1.0]], stress_shocks=[[0.01, -0.02]])
    assert s.gross == 200.0 and s.net == 0.0
    assert s.var_95 >= 0 and s.es_95 >= s.var_95 - 1e-9
    assert 0 <= s.liquidity_frac <= 1.0 and s.concentration_hhi > 0


def test_reverse_stress_brackets_loss():
    out = reverse_stress([100.0, -50.0], target_loss=15.0,
                         shock_grid=[0.01, 0.05, 0.1, 0.2])
    assert out and min(abs(l - 15.0) for _, l in out) < 15.0
    v, e = var_es([], 0.05)
    assert (v, e) == (0.0, 0.0)


# ---- H. agent stack ----
from agents.research_stack import (
    PermissionLayer,
    ResearchPlanner,
    Sandbox,
    ToolRegistry,
)


def test_agent_no_r1_to_r5_jump():
    perm = PermissionLayer("R1")
    assert perm.allow_tool("read_market")[0] is True
    assert perm.allow_tool("submit_live")[0] is False
    ok, _ = perm.request_promotion("R5", True)
    assert ok is False and perm.agent_level == "R1"
    ok, msg = perm.request_promotion("R2", True)
    assert ok is True and "EXPERIMENT" in msg
    ok, _ = perm.request_promotion("R3", False)
    assert ok is False  # fail-closed


def test_sandbox_blocks_unregistered_and_unpermitted():
    perm = PermissionLayer("R2")
    reg = ToolRegistry()
    reg.register("run_backtest", "img-v1")
    sb = Sandbox()
    assert sb.execute("run_backtest", "payload", permission=perm, registry=reg)[0] is True
    assert sb.execute("submit_live", "x", permission=perm, registry=reg)[0] is False
    assert sb.execute("run_experiment", "x", permission=perm, registry=reg)[0] is False
    try:
        reg.register("hack_tool", "evil")
        assert False
    except ValueError:
        pass
    assert ResearchPlanner().plan("h", intent="shadow").max_level == "R4"


# ---- I. knowledge graph ----
from research.knowledge_graph import KGNode, QuantKnowledgeGraph


def test_knowledge_graph_invalidation_query():
    g = QuantKnowledgeGraph()
    g.add(KGNode("d1", "Dataset", "ticks"))
    g.add(KGNode("f1", "Feature", "mom"), ["d1"])
    g.add(KGNode("a1", "Alpha", "MOM-471"), ["f1"])
    g.add(KGNode("e1", "Experiment", "exp", "invalidated"), ["a1"])
    g.add(KGNode("e2", "Experiment", "exp2", "validated"), ["a1"])
    assert g.invalidated_by("a1") == ["e1"]
    assert "d1" in g.decision_trail("e1")
    try:
        g.add(KGNode("x", "Vibe", "?"))
        assert False
    except ValueError:
        pass


# ---- J. reproducibility ----
from research.reprodex import ReproducibilityStore


def test_reproducibility_id_roundtrip():
    store = ReproducibilityStore()
    manifest = {"code": "abc", "data": "ticks-v1", "features": "f", "model": "m",
                "parameters": "{}", "environment": "py312", "seed": 7,
                "execution_model": "l3", "risk_model": "limits"}
    rid = store.mint(1842, manifest)
    assert rid.experiment_id == "EXP-2026-00001842"
    ok, out = store.reproduce(rid.experiment_id, lambda m: m["seed"] * 2)
    assert ok is True and out == 14
    assert store.reproduce("EXP-2026-99999999", lambda m: 0)[0] is False


# ---- K. lifecycle + drift ----
from research.model_lifecycle import DriftMonitor, ModelLifecycle


def test_lifecycle_no_manual_jumps():
    m = ModelLifecycle("m1")
    assert m.transition("PAPER", gate_passed=True)[0] is False
    assert m.transition("VALIDATED", gate_passed=False)[0] is False
    assert m.transition("VALIDATED", gate_passed=True)[0] is True
    assert m.transition("PAPER", gate_passed=True)[0] is True
    assert m.transition("PRODUCTION", gate_passed=True)[0] is False  # via SHADOW only
    assert m.transition("RETIRED", gate_passed=False)[0] is True  # retire always allowed


def test_drift_escalation_to_retrain():
    d = DriftMonitor()
    d.set_baseline("ic", 0.05, 0.01)
    assert d.observe({"ic": 0.055}) == "NORMAL"
    assert d.observe({"ic": 0.075}) == "WARNING"
    assert d.observe({"ic": 0.085}) == "DEGRADED"
    assert d.observe({"ic": 0.095}) == "PAUSED"
    assert d.observe({"ic": 0.12}) == "RETRAIN"
    try:
        d.set_baseline("vibes", 0, 1)
        assert False
    except ValueError:
        pass


# ---- M+N. failure injection + secrets ----
from operations.failure_injection import (
    FailSafeStub,
    FailureInjector,
    SecretVault,
    audit_secret_path,
)


def test_failure_injection_all_safe():
    res = FailureInjector().inject(FailSafeStub())
    assert len(res) == 11
    assert FailureInjector().all_safe(res) is True


def test_secrets_never_in_env_or_git():
    v = SecretVault()
    c = v.mint("trade", "paper", ttl_s=900)
    assert v.valid(c) is True
    assert audit_secret_path("vault://prod/broker")[0] is True
    for bad in [".env", "config.yaml", "source code leak", "git history"]:
        assert audit_secret_path(bad)[0] is False


# ---- O. telemetry ----
from observability.telemetry import Telemetry


def test_telemetry_ratios_and_prometheus():
    t = Telemetry()
    t.inc("orders", 100)
    t.inc("fills", 90)
    t.inc("rejects", 5)
    t.set_gauge("pnl", 123.4)
    t.observe("execution_latency_ns", 500)
    t.span("decide", 900, model="m1")
    assert t.fill_ratio() == 0.9 and t.rejection_rate() == 0.05
    prom = t.to_prometheus()
    assert "delta_orders_total 100" in prom and "delta_execution_latency_ns_p50 500" in prom
    try:
        t.inc("nope")
        assert False
    except ValueError:
        pass


# ---- P+Q. kernel bench + differential ----
from benchmarks.kernel_bench import DifferentialSuite, bench_kernel, bench_table


def test_kernel_bench_table_is_measured():
    r = bench_kernel("lob_insert", "python", lambda: sum(range(50)), n=200)
    assert r.n == 200 and r.p50_ns <= r.p95_ns <= r.p99_ns <= r.p999_ns
    assert r.p50_ns > 0 and "machine:" in bench_table([r])


def test_differential_honest_about_missing_native():
    s = DifferentialSuite()
    s.add("add", (1, 2), lambda a, b: a + b, lambda a, b: a + b)
    s.add("edge", (), lambda: 0, None)
    rep = s.report()
    assert rep["parity"] is True and rep["missing_native"] == ["edge"]
    s2 = DifferentialSuite()
    s2.add("mismatch", (1,), lambda x: x, lambda x: x + 1)
    assert s2.report()["parity"] is False


# ---- R. ablation ----
from research.ablation_study import ARMS, run_ablation


def test_ablation_defensible_gains():
    out = run_ablation(lambda arm: 0.5 + (0.2 if arm.regime else 0)
                       + (0.15 if arm.microstructure else 0)
                       + (0.1 if arm.adaptive_execution else 0))
    assert out["monotonic"] == 1.0
    assert out["delta_regime"] > 0 and out["delta_micro"] > 0 and out["delta_full"] > 0
    assert len(ARMS) == 4


# ---- S. evidence ledger ----
from validation.evidence_ledger import EvidenceLedger, EvidenceRecord


def _rec(**kw):
    base = dict(experiment="E1", dataset="D", period="2020-24", oos_sharpe=1.2,
                cost_bps=3.0, capacity_usd=1e7, dsr=0.9, pbo=0.2, drawdown=0.05,
                stress_passed=True, benchmark_sharpe=0.3, ci_low=0.4, ci_high=1.8)
    base.update(kw)
    return EvidenceRecord(**base)


def test_ledger_decides_not_asserts():
    led = EvidenceLedger()
    assert led.verdict("E1")["passed"] is False
    led.submit(_rec())
    assert led.verdict("E1")["passed"] is True
    led.submit(_rec(experiment="E2", ci_low=-0.1))
    assert led.verdict("E2")["passed"] is False
    led.submit(_rec(experiment="E3", stress_passed=False))
    assert led.verdict("E3")["checks"]["stress"] is False


# ---- T. long duration ----
from validation.long_duration import LongDurationTracker


def test_long_duration_honest_about_bars():
    t = LongDurationTracker()
    for i in range(10):
        t.record(pp=100 + i, ap=100 + i + 0.1, pf=100.0, af=100.05,
                 pc=2.0, ac=2.5, pr=0.01, ar=0.012)
    c = t.compare(required_bars=10_000)
    assert c["bars"] == 10 and c["sufficient_duration"] is False
    assert c["mae_price"] > 0
    assert t.promote_to_shadow(paper_ok=False) is False
    assert t.promote_to_shadow(paper_ok=True) is True and t.stage == "SHADOW"
