"""Launch slice Waves 1-5: sessions/market/PIT/lake/quality/ref/micro/latency/cost/
scenarios/alpha/validation/capacity/world/ML/portfolio/risk/OMS/agent/prod."""
from data.engineering.gates import manifest_hash, quality_gate, reference_version
from data.market.canonical import FeedHealth, Tick, route_badge
from data.pit.gate import check_chain, dataset_sha, reproduce_manifest
from delta_tui.state.session import SessionManager
from execution.oms_unify import IdempotencyStore, certify, next_hypothesis
from execution.realism import calibrate_cost, replay_events_to_book
from research.alpha_lab import AlphaEntry, AlphaRegistry, capacity_check, scenario_manifest, validation_report
from research.world_portfolio import ModelCard, ModelRegistry, classify_regime, enforce_caps, risk_limits


def test_g10_session_ext(tmp_path):
    m = SessionManager(db_path=str(tmp_path / "s.sqlite"))
    s = m.new("PAPER", "NVDA")
    h = m.set_mandate(s.session_id, {"cap": 1})
    assert h
    m.rename(s.session_id, "AAPL")
    assert m.export(s.session_id)["universe"] == "AAPL"
    f = m.fork(s.session_id)
    assert m.diff(s.session_id, f.session_id)["mandate_drift"] is False
    assert m.retention(90) >= 0


def test_g11_market():
    t = Tick("NVDA", 100.0, 10, 1.0, "live", 1.0)
    assert route_badge("live").startswith("SOURCE/live")
    assert route_badge("synthetic").endswith("DEMO")
    fh = FeedHealth(last_as_of=0.0)
    assert fh.check(now=100.0) == "DOWN"


def test_g12_pit():
    check_chain(1, 2, 3, 4, 5)
    try:
        check_chain(5, 2, 3, 4, 6)
        assert False
    except ValueError:
        pass
    assert len(dataset_sha([{"a": 1}])) == 64
    assert reproduce_manifest("E1", "c", "d")["replays_pit_exactly"] is False  # P-1.5: unverified without records
    recs = [{"a": 1}]
    assert reproduce_manifest("E1", "c", dataset_sha(recs), recs)["replays_pit_exactly"] is True
    assert reproduce_manifest("E1", "c", "deadbeef", recs)["replays_pit_exactly"] is False


def test_g131415_gates():
    assert len(manifest_hash({"a": 1})) == 64
    assert not quality_gate(5, 5, True).ok
    assert quality_gate(0, 0, False).ok
    assert reference_version({"v": 1})


def test_g161718_realism():
    class B:
        bids = {}
        asks = {}
    r = replay_events_to_book([{"side": "bid", "price": 100, "qty": 5}], B())
    assert r["bid"] == 100 and r["n"] == 1
    assert calibrate_cost(5, 5, 12)["err_bps"] == 2
    assert scenario_manifest("2008", "abc")["sha"]


def test_g2023_alpha():
    reg = AlphaRegistry()
    reg.register(AlphaEntry("a1", "momentum"))
    assert reg.coverage()["families"] == 10
    assert reg.retire_on_decay("a1", 200) is True
    assert validation_report("E1", 0.05, 0.8, 0.3)["verdict"] == "pass"
    assert not capacity_check(1000, 500)["ok"]
    assert capacity_check(10000, 100)["ok"]


def test_g2427_world():
    assert classify_regime(0.5, 0.8).regime == "stress"
    mr = ModelRegistry()
    try:
        mr.promote(ModelCard("m1", "d", False))
        assert False
    except ValueError:
        pass
    mr.promote(ModelCard("m1", "d", True))
    assert enforce_caps({"a": 0.5})["a"] <= 0.2
    assert not risk_limits(5.0, 0.2)["ok"]
    assert risk_limits(1.0, 0.01)["ok"]


def test_g2830_oms():
    import tempfile, os
    p = os.path.join(tempfile.gettempdir(), "idem_test.sqlite")
    try:
        os.remove(p)
    except Exception:
        pass
    s = IdempotencyStore(p)
    assert s.claim("c1", "o1") is True
    assert s.claim("c1", "o2") is False
    assert "liquidity" in next_hypothesis(["liquidity break"])
    assert certify({g: True for g in ["R0", "R1"]}) == "R2"
