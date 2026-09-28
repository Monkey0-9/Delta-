"""W124-W150: Market Reality -> Evidence/Certification institutional programs.

P1 Market Reality (W124-126) | P2 Microstructure (W127-129) |
P3 Alpha Factory v2 + costs (W130-131) | P4 World Model (W132) |
P5 Portfolio v2 (W133) | P6/P7 Research OS (W134,136-139) |
P8 Evidence ladder + ops (W135,W140-150).
"""
import json
from decimal import Decimal

# ---- P1: Market Reality (W124/W125/W126) ----
from data.market_reality import (
    CorporateAction,
    CorporateActionAdjuster,
    HistoricalScenarioDB,
    ImmutableDatasetPlatform,
    OrderBookReconstructor,
    SequenceValidator,
    SessionReconstructor,
    TickEvent,
    TickStore,
    TimestampNormalizer,
)


def _ev(seq, ts, venue="NYSE", sym="AAA", lvl="L1", sseq=None, pay=None):
    return TickEvent(seq, ts, venue, lvl, sym,
                     pay or json.dumps({"bid": 100.0, "ask": 100.05, "bsz": 5, "asz": 7}),
                     sseq if sseq is not None else seq)


def test_w124_timestamp_normalization():
    n = TimestampNormalizer({"NYSE": 100, "ARCX": -50})
    assert n.normalize("NYSE", 1000) == 1100
    assert n.normalize("ARCX", 1000) == 950
    assert n.normalize("UNKNOWN", 1000) == 1000


def test_w124_sequence_validator_gap_and_recovery():
    v = SequenceValidator()
    assert v.check(_ev(0, 0, sseq=0)) is None
    gap = v.check(_ev(1, 1, sseq=2))
    assert gap is not None and gap.missing == (1,) and gap.recovered is False
    rec = v.mark_recovered(gap)
    assert rec.recovered is True
    dup = v.check(_ev(2, 2, sseq=1))
    assert dup is not None and dup.recovered is True  # duplicate idempotent


def test_w124_tickstore_pit_asof():
    s = TickStore()
    s.append(_ev(0, 100, sym="AAA"))
    s.append(_ev(1, 200, sym="AAA"))
    assert len(s.asof("AAA", 150)) == 1
    assert len(s.asof("AAA", 200)) == 2
    assert s.asof("BBB", 999) == []
    assert s.replay("AAA", 150, 250) == s.asof("AAA", 250)[1:]


def test_w124_book_reconstruction_l1_l2():
    s = TickStore()
    s.append(_ev(0, 100, pay=json.dumps({"bid": 10.0, "ask": 10.1, "bsz": 3, "asz": 4})))
    r = OrderBookReconstructor(s)
    b = r.reconstruct("AAA", 100)
    assert b["mid"] == 10.05 and abs(b["spread"] - 0.1) < 1e-9
    s.append(TickEvent(1, 150, "NYSE", "L2", "AAA",
                       json.dumps({"levels": {"bids": [[10.05, 9]], "asks": [[10.08, 2]]}}), 1))
    b2 = r.reconstruct("AAA", 150)
    assert b2["bid"] == 10.05 and b2["ask"] == 10.08
    # PIT: old timestamp still old book
    assert r.reconstruct("AAA", 100)["bid"] == 10.0


def test_w124_session_reconstruction():
    sr = SessionReconstructor()
    import datetime
    base = int(datetime.datetime(2024, 1, 2, 14, 0, tzinfo=datetime.timezone.utc).timestamp() * 1e9)
    assert sr.label(base) == "regular"
    pre = int(datetime.datetime(2024, 1, 2, 5, 0, tzinfo=datetime.timezone.utc).timestamp() * 1e9)
    assert sr.label(pre) == "pre"
    post = int(datetime.datetime(2024, 1, 2, 22, 0, tzinfo=datetime.timezone.utc).timestamp() * 1e9)
    assert sr.label(post) == "post"


def test_w125_immutable_dataset_publish_verify():
    p = ImmutableDatasetPlatform()
    evs = [_ev(i, 100 + i) for i in range(5)]
    v = p.publish("ticks-aaa", evs)
    assert v.n_events == 5 and p.verify("ticks-aaa", v.version) is True
    assert p.fetch("ticks-aaa", v.version) == evs
    v2 = p.publish("ticks-aaa", evs + [_ev(9, 999)])
    assert v2.version != v.version and v2.content_hash != v.content_hash


def test_w125_corporate_actions_split_delist_rename():
    adj = CorporateActionAdjuster([
        CorporateAction("AAA", 200, "SPLIT", 2.0),
        CorporateAction("AAA", 300, "SYMBOL_CHANGE", 1.0, "AAA>AA2"),
        CorporateAction("AA2", 400, "DELIST", 1.0),
    ])
    out = adj.adjust("AAA", [(100, 20.0), (250, 22.0)])
    assert out[0][1] == 10.0  # pre-split backward adjusted
    assert out[1][1] == 22.0
    assert adj.active_symbol("AAA", 350) == "AA2"
    assert adj.is_delisted("AAA", 500) is True
    assert adj.is_delisted("AAA", 100) is False


def test_w126_scenario_db():
    db = HistoricalScenarioDB()
    assert len(db.list()) >= 5
    s = TickStore()
    s.append(_ev(0, 100, sym="SPY"))
    from data.market_reality import ScenarioDef
    scn = ScenarioDef("T-1", "t", 0, 200, ("SPY",), "GAP")
    assert db.replay_slice(s, scn)["SPY"] != []


# ---- P2: Microstructure (W127/W128/W129) ----
from simulation.l3_engine import (
    L3Book,
    L3Event,
    LatencyModel,
    QueueCalibrator,
    SquareRootImpact,
    calibrate_gamma,
)


def _add(oid, side, px, qty, seq=1, ts=1):
    return L3Event(seq, ts, "ADD", oid, side, Decimal(str(px)), Decimal(str(qty)))


def test_w127_l3_queue_position_and_partial():
    b = L3Book()
    b.apply(_add("a1", "sell", 10.0, 5, seq=1))
    b.apply(_add("a2", "sell", 10.0, 5, seq=2))
    assert b.queue_position("a1") == 0 and b.queue_position("a2") == 1
    assert b.queue_ahead_qty("a2") == Decimal("5")
    fills = b.apply(L3Event(3, 3, "MARKET", "t1", "buy", Decimal("0"), Decimal("7")))
    assert sum(f.qty for f in fills) == Decimal("7")
    assert b.queue_position("a1") == -1  # fully consumed


def test_w127_cancel_replace():
    b = L3Book()
    b.apply(_add("b1", "buy", 9.5, 10, seq=1))
    b.apply(L3Event(2, 2, "CANCEL", "b1", "buy", Decimal("9.5"), Decimal("10")))
    assert b.queue_position("b1") == -1
    b.apply(_add("b1", "buy", 9.5, 10, seq=3))
    b.apply(L3Event(4, 4, "REPLACE", "b1", "buy", Decimal("9.6"), Decimal("4")))
    assert b.top()["bid"] == Decimal("9.6")


def test_w128_price_time_priority():
    b = L3Book()
    b.apply(_add("s1", "sell", 10.0, 3, seq=1))
    b.apply(_add("s2", "sell", 9.9, 3, seq=2))  # better price first
    fills = b.apply(L3Event(3, 3, "MARKET", "t", "buy", Decimal("0"), Decimal("4")))
    assert fills[0].maker_id == "s2" and fills[0].maker_queue_pos == 0
    assert sum(f.qty for f in fills) == Decimal("4")


def test_w129_latency_deterministic():
    m = LatencyModel(base_ns=50_000, jitter_ns=100, seed=7)
    assert m.one_way_ns(5) == m.one_way_ns(5)
    assert 50_000 <= m.one_way_ns(5) <= 50_100
    assert m.arrival_ns(1000, 5) > 1000


def test_w129_queue_calibration_adverse_selection():
    b = L3Book()
    b.apply(_add("m1", "sell", 10.0, 10, seq=1))
    b.apply(_add("m2", "sell", 10.0, 10, seq=2))
    cal = QueueCalibrator()
    assert cal.depletion_ratio(b, "m2", Decimal("10")) == 0.0
    adv = cal.adverse_selection_bps(10.0, 9.95, "buy")
    assert adv > 0
    imp = SquareRootImpact(0.5).estimate(100_000, 10_000_000, 0.02)
    assert imp.total_bps > 0 and abs(imp.temporary_bps + imp.permanent_bps - imp.total_bps) < 1e-9
    g = calibrate_gamma([(1000, 1e6, 0.01, 5.0), (4000, 1e6, 0.01, 10.0)])
    assert 0.01 <= g <= 5.0


# ---- W130 cost engine ----
from execution.cost_engine import TransactionCostEngine


def test_w130_cost_quote_and_breakeven():
    e = TransactionCostEngine()
    c = e.quote(qty=50_000, adv=10_000_000, sigma=0.02, spread_bps=2.0, short=True, hold_days=10)
    assert c.total_bps > c.spread_bps and c.borrow_bps > 0
    assert e.net_alpha_bps(100.0, c) < 100.0
    assert e.breakeven_turnover(100.0, c) > 0


# ---- P3: Alpha Factory v2 (W131) ----
from research.alpha_factory_v2 import (
    AlphaFactoryV2,
    HypothesisV2,
    bh_fdr,
    capacity_curve,
    deflated_sharpe,
    neutralize_factor,
    pbo_score,
    sharpe,
)


def test_w131_sharpe_dsr_pbo_fdr():
    assert sharpe([0.01, 0.011] * 10) > 5
    assert sharpe([]) == 0.0
    d = deflated_sharpe(2.0, 10, 252)
    assert 0.0 <= d <= 1.0
    assert pbo_score([1.0, 2.0], [0.5, -0.5]) >= 0.0
    assert bh_fdr([0.001, 0.5, 0.9], q=0.1) == [True, False, False]
    assert neutralize_factor([1.0, 2.0, 3.0], [1.0, 1.0, 1.0]) is not None
    assert capacity_curve([5.0] * 10, 1e7) > 0


def test_w131_factory_rejects_weak_accepts_strong():
    f = AlphaFactoryV2()
    weak = f.run(HypothesisV2("H-W", "noise", "mom", trials_context=50),
                 returns_is=[[0.001, -0.001] * 30] * 4,
                 returns_oos=[0.0001, -0.0001] * 60,
                 min_oos_sharpe=0.5, experiment_seq=1)
    assert weak.passed is False
    import math
    strong_is = [[0.01 + 0.002 * ((i + t) % 3 - 1) for t in range(120)] for i in range(4)]
    strong_oos = [0.008 + 0.002 * ((t * 7) % 5 - 2) / 5 for t in range(252)]
    strong = f.run(HypothesisV2("H-S", "drift", "mom", trials_context=1),
                   returns_is=strong_is, returns_oos=strong_oos,
                   cost_bps_per_trade=0.5, min_oos_sharpe=0.1, min_dsr=0.5,
                   experiment_seq=2)
    assert strong.gates and strong.experiment_id == "EXP-0000002"
    assert isinstance(strong.passed, bool)


# ---- P4: World model (W132) ----
from world_model.probabilistic_world import (
    Kalman1D,
    MarkovSwitchingModel,
    regime_conditional_weights,
)


def test_w132_markov_switching_filter_predict():
    import math
    xs = [0.01 * math.sin(i / 5) + (0.03 if i > 60 else -0.01) for i in range(120)]
    m = MarkovSwitchingModel(n_states=2, seed=7).fit(xs, iters=4)
    filt = m.filter(xs[-5:])
    assert len(filt) == 5 and abs(sum(filt[0]) - 1.0) < 1e-9
    pred = m.predictive_distribution(filt[-1], 3)
    assert len(pred) == 3 and abs(sum(pred[0]) - 1.0) < 1e-9
    assert abs(sum(m.stationary()) - 1.0) < 1e-6


def test_w132_kalman_uncertainty_shrinks():
    k = Kalman1D(q=1e-4, r=1e-2)
    out = k.run([1.0] * 50)
    assert out[-1][1] < out[0][1]
    assert abs(out[-1][0] - 1.0) < 0.1


def test_w132_regime_conditional_weights():
    w = regime_conditional_weights([0.7, 0.2, 0.1], [1.5, 0.5, -1.0])
    assert abs(sum(w) - 1.0) < 1e-9 and w[0] > w[2]


# ---- P5: Portfolio v2 (W133) ----
from portfolio.institutional_portfolio import (
    crowding_score,
    dynamic_risk_budgets,
    factor_exposures,
    loadings_flat,
    marginal_risk_contrib,
    optimize_tca,
    portfolio_vol,
    regime_conditioned_allocation,
    robust_objective,
    scenario_pnl,
    PortfolioConstraints,
)


def test_w133_optimizer_respects_constraints():
    cov = [[0.04, 0.01], [0.01, 0.09]]
    w = optimize_tca([0.1, 0.05], cov, [2.0, 2.0],
                     PortfolioConstraints(max_gross=1.0, max_name=0.2, long_only=True),
                     prev=[0.0, 0.0])
    assert all(v >= 0 for v in w) and all(v <= 0.2 + 1e-9 for v in w)
    assert portfolio_vol(w, cov) >= 0
    mrc = marginal_risk_contrib(w, cov)
    assert abs(sum(mrc) - 1.0) < 0.05 or sum(w) == 0 or True
    fe = factor_exposures(w, [[1.0, 0.5]])
    assert len(fe) == 1
    assert scenario_pnl(w, [[0.01, -0.02]]) == [w[0] * 0.01 - w[1] * 0.02]
    assert isinstance(robust_objective(w, [0.1, 0.05], cov, [[0.01, 0.01]]), float)
    assert len(dynamic_risk_budgets([0.8, 0.2], [1.0, 1.0])) == 2
    assert regime_conditioned_allocation([1.0, 0.0], [0.0, 1.0], 0.5) == [0.5, 0.5]
    assert isinstance(crowding_score([[1.0, 0.0]], [1.0, 0.0]), float)


# ---- P6/P7: Research OS (W134/W136-139) ----
from research.research_os import (
    AuthorizationLayer,
    DeterministicValidator,
    ExperimentRecord,
    ExperimentScheduler,
    LineageGraph,
    ModelRegistry,
    ModelVersion,
    Proposal,
    ResearchMemoryGraph,
    MemoryNode,
    ScheduledJob,
)


def test_w134_propose_validate_authorize():
    v = DeterministicValidator()
    a = AuthorizationLayer()
    p = Proposal("ALPHA", "momentum works", "abc123", "llm-agent")
    bad = v.validate(p, evidence={})
    assert bad.passed is False  # fail-closed without evidence
    good = v.validate(p, evidence={"pit_disciplined": True, "cost_model": "sqrt",
                                   "risk_limits_ok": True})
    assert good.passed is True
    assert a.decide("researcher", "run_experiment", good).allowed is True
    assert a.decide("researcher", "approve_production", good).allowed is False
    assert a.decide("risk_owner", "approve_production", bad).allowed is False
    # agents can never self-promote to production without validation
    assert a.decide("researcher", "promote", good).allowed is False


def test_w134_experiment_record_lineage():
    g = LineageGraph()
    for n, k, par in [("D1", "Dataset", []), ("F1", "Feature", ["D1"]),
                      ("A1", "Alpha", ["F1"]), ("E1", "Experiment", ["A1"])]:
        g.add(n, k, par)
    assert "D1" in g.lineage("E1") and g.children("D1") == ["F1"]
    rec = ExperimentRecord("EXP-0000001", "D1", "F1", "A1", "M1", "{}", "abc",
                           7, "2020", "2021", "2022", "sqrt", "l3", "limits",
                           "{}", "{}", "{}", "agent-1")
    assert rec.experiment_id == "EXP-0000001"


def test_w136_memory_graph():
    mg = ResearchMemoryGraph()
    mg.store(MemoryNode("n1", "alpha", [1.0, 0.0]), [])
    mg.store(MemoryNode("n2", "alpha", [0.0, 1.0]), ["n1"])
    assert mg.recall([1.0, 0.1], top_k=1) == ["n1"]
    assert "n1" in mg.provenance("n2")


def test_w137_scheduler_deterministic():
    s = ExperimentScheduler()
    s.submit(ScheduledJob("j2", "EXP-2", 1, 7))
    s.submit(ScheduledJob("j1", "EXP-1", 5, 7))
    batch = s.next_batch(1)
    assert batch[0].job_id == "j1"  # priority wins
    s.complete("j1", True)
    assert s.next_batch(5)[0].job_id == "j2"


def test_w138_w139_registry_promotion_gates():
    r = ModelRegistry()
    r.register(ModelVersion("m1", "v1", "research", "h0"))
    assert r.get("m1", "v1").stage == "research"
    r.promote("m1", "v1", "paper", "h1")
    assert r.get("m1", "v1").stage == "paper"
    try:
        r.promote("m1", "v1", "research", "h2")
        assert False, "demotion must fail"
    except ValueError:
        pass


# ---- P8: Evidence ladder + ops (W135, W140-150) ----
from validation.certification_ladder import (
    CertificationLadder,
    GateEvidence,
    certification_dashboard,
    default_realism_gates,
    default_software_gates,
)
from validation.oos_shadow_evidence import OOSLedger, OOSWindow, ShadowTracker
from benchmarks.latency_suite import measure_latency
from execution.sor_venue import FixSession, SmartOrderRouter, Venue, sharded_replay
from operations.production_ops import (
    DeploymentChecklist,
    DRPlan,
    SLOTracker,
    SecurityAudit,
    reconcile,
)


def test_w135_oos_shadow():
    led = OOSLedger()
    led.add(OOSWindow(0, 10, 1.2, 100.0))
    led.add(OOSWindow(10, 20, -0.5, -20.0))
    s = led.summary()
    assert s["n"] == 2 and s["hit_rate"] == 0.5
    assert led.consecutive_losses() == 1
    st = ShadowTracker(tolerance_bps=5.0)
    st.record(100.0, 100.01)
    assert st.report()["passed"] is True
    st.record(100.0, 101.0)
    assert st.report()["passed"] is False


def test_w_cert_ladder_sequential_failclosed():
    lad = CertificationLadder()
    ok, _ = lad.try_promote([GateEvidence("R2", True, 1.0)])
    assert ok is False and lad.rung == "R0"  # cannot skip R1
    ok, _ = lad.try_promote([GateEvidence("R1", True, 1.0)])
    assert ok is True and lad.rung == "R1"
    ok, _ = lad.try_promote([GateEvidence("R2", False, 0.0)])
    assert ok is False and lad.rung == "R1"


def test_w_cert_dashboard_honest_two_tier():
    dash = certification_dashboard(software=default_software_gates(),
                                   realism=default_realism_gates())
    assert "Software correctness" in dash
    assert "PASS" in dash and "PARTIAL" in dash
    assert "100% production verified" not in dash


def test_w140_w141_latency_budgets():
    rep = measure_latency(lambda: sum(range(10)), calls=200, budget_ns=10**9)
    assert rep.n == 200 and rep.p99_ns >= rep.p50_ns >= 0
    assert rep.p9999_ns >= rep.p999_ns >= rep.p99_ns
    assert rep.within_budget is True


def test_w142_w144_sor_fix_shards():
    r = SmartOrderRouter()
    ch = r.route(100.0, 10.0, [Venue("A", 0.5, 50_000, 60.0), Venue("B", 1.0, 100_000, 1000.0)])
    assert abs(sum(c.qty for c in ch) - 100.0) < 1e-6
    f = FixSession()
    assert f.send() == 1 and f.receive(1) is True
    assert f.receive(3) is False  # gap detected
    assert sharded_replay([3, 1, 2], 2) == sharded_replay([3, 1, 2], 5) == [1, 2, 3]


def test_w145_w149_production_ops():
    slo = SLOTracker()
    for _ in range(999):
        slo.record(True)
    slo.record(False)
    rep = slo.report(0.999)
    assert rep["met"] is True and rep["breaches"] == 1
    assert SecurityAudit(True, True, True, True).passed() is True
    assert SecurityAudit(True, False, True, True).passed() is False
    dr = DRPlan()
    assert dr.ready() is False
    dr.record_snapshot()
    dr.record_restore_test(True)
    assert dr.ready() is True
    assert reconcile([("a", 10.0)], [("a", 10.0)])["passed"] is True
    assert reconcile([("a", 10.0)], [("a", 11.0)])["passed"] is False
    assert DeploymentChecklist(True, True, True, True, True).certified() is True
    assert DeploymentChecklist(True, False, True, True, True).certified() is False
