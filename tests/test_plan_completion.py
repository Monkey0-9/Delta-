"""Plan-completion gates: research memory, lifecycle, event backtest, paper track."""
from __future__ import annotations


def test_research_memory_records_recalls_lineage():
    from research.real_loop import research_memory as RM

    m = RM.ResearchMemory()
    m.record("E1", "momentum works in low-vol regimes", ("AAPL",),
             {"AAPL": "h1"}, "f-v2", "a-v2", {"ic": 0.05}, stage="concluded",
             conclusion="confirmed OOS")
    m.record("E2", "momentum fails in high-correlation regimes", ("MSFT",),
             {"MSFT": "h2"}, "f-v2", "a-v2", {"ic": -0.01}, stage="failed",
             conclusion="crowded, invalidated", parent_experiment_id="E1")
    hits = m.recall("momentum regimes")
    assert {h["exp_id"] for h in hits} == {"E1", "E2"}
    assert [c["exp_id"] for c in m.lineage("E2")] == ["E1", "E2"]
    assert m.failures()[0]["exp_id"] == "E2"
    assert m.verify("E1") and m.verify("E2")


def test_research_memory_rejects_vacuous_and_cycles():
    import pytest

    from research.real_loop import research_memory as RM

    m = RM.ResearchMemory()
    with pytest.raises(ValueError):
        m.record("E0", "   ", ("A",), {}, "f", "a", {})
    with pytest.raises(ValueError):
        m.record("E0", "h", ("A",), {}, "f", "a", {}, stage="nope")
    m.record("A", "hyp a", ("X",), {}, "f", "a", {}, parent_experiment_id="B")
    m.record("B", "hyp b", ("X",), {}, "f", "a", {}, parent_experiment_id="A")
    with pytest.raises(ValueError):
        m.lineage("A")


def test_lifecycle_gates_and_no_jump():
    import pytest

    from research.real_loop import model_lifecycle as LC

    lc = LC.ModelLifecycle()
    lc.register("m1", "v1", "hash1", actor="r")
    ev = LC.GateEvidence(stats_gate_pass=False, wf_gate_pass=False)
    with pytest.raises(LC.LifecycleError):
        lc.promote("m1", "v1", "candidate", ev)
    # illegal jump research->production forbidden even with perfect evidence
    full = LC.GateEvidence(True, True, paper_net=0.1, benchmark_net=0.01,
                           approver="boss")
    with pytest.raises(LC.LifecycleError):
        lc.promote("m1", "v1", "production", full)
    lc.promote("m1", "v1", "candidate", LC.GateEvidence(True, True))
    assert lc.stage_of("m1", "v1") == "candidate"
    with pytest.raises(LC.LifecycleError):  # no approver
        lc.promote("m1", "v1", "shadow", LC.GateEvidence(True, True, paper_net=0.05))
    lc.promote("m1", "v1", "shadow", LC.GateEvidence(True, True, paper_net=0.05,
                                                     approver="boss"))
    lc.promote("m1", "v1", "production", full)
    assert lc.stage_of("m1", "v1") == "production"
    with pytest.raises(LC.LifecycleError):  # deprecation needs reason
        lc.promote("m1", "v1", "deprecated", LC.GateEvidence(True, True))
    lc.promote("m1", "v1", "deprecated",
               LC.GateEvidence(True, True, reason="alpha decayed"))
    assert len(lc.history("m1")) == 5


def test_event_backtest_deterministic_and_pit():
    import pytest

    from research.real_loop import event_backtest as EB
    from research.real_loop import features as F
    from research.real_loop import market_data as M

    bars = M.synthetic_bars("EBT", days=200).frame
    feat = F.compute_features(bars, "EBT", "ebhash")
    sig_cols = [c for c in feat.columns if c.startswith(("mom_", "mr_z_", "trend_"))]
    tgt = (((feat[sig_cols].mean(axis=1).fillna(0) > 0.5).astype(float) -
            (feat[sig_cols].mean(axis=1).fillna(0) < -0.5).astype(float)
            ).shift(2).fillna(0) * 10)
    r1 = EB.run_event_backtest(bars, tgt, seed=9)
    r2 = EB.run_event_backtest(bars, tgt, seed=9)
    assert r1["curve"] == r2["curve"] and r1["final_equity"] == r2["final_equity"]
    assert r1["bars"] == len(bars) - 80 and r1["total_fills"] > 0
    assert r1["microstructure"].startswith("synthetic-ladder")
    with pytest.raises(ValueError):
        EB.run_event_backtest(bars, tgt.iloc[::-1], seed=9)


def test_paper_track_symbol_row(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_MODE", "SIMULATION")
    from scripts.paper_track import run_symbol

    r = run_symbol("AA.PL", days=200, seed=5)
    assert r["source"] == "synthetic_offline"
    for k in ("ic", "dsr", "wf_gate", "eb_net", "eb_sharpe", "buy_hold", "stats_gate"):
        assert k in r
