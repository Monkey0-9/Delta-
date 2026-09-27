"""Genuine verification for delta_omega: no mocks, asserts on math properties."""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import numpy as np
import pytest

from delta_omega.pit import PITRecord, PITStore, SecurityMaster, adjust_price
from delta_omega.alpha_risk import (
    orthogonalize, deflated_sharpe, require_dsr, cpcv_splits, pbo,
    ledoit_wolf_shrinkage, factor_portfolio_var, evt_var_es, reverse_stress,
)
from delta_omega.portfolio_exec import (
    mean_variance, hrp_weights, bs_price, sabr_iv, ofi_tick, microprice,
    almgren_chriss, sor_split, sqrt_impact_cost,
)
from delta_omega.agent_ledger_gate import (
    Supervisor, ToolCall, Ledger, Fill, GateState, red_button,
)

NOW = datetime.now(timezone.utc)

def test_pit_no_lookahead():
    s = PITStore()
    s.insert("A", "close", PITRecord(100.0, NOW - timedelta(days=2), NOW - timedelta(days=1), NOW - timedelta(hours=1)))
    with pytest.raises(LookupError):
        s.point_in_time("A", "close", NOW - timedelta(days=3))  # not yet knowable
    assert s.point_in_time("A", "close", NOW) == 100.0

def test_pit_clock_inversion_rejected():
    s = PITStore()
    with pytest.raises(ValueError):
        s.insert("A", "close", PITRecord(1.0, NOW, NOW - timedelta(hours=1), NOW))

def test_security_master_survivorship():
    sm = SecurityMaster()
    sm.register("UID1", ["AAA"], NOW - timedelta(days=365 * 10), NOW - timedelta(days=100))
    sm.register("UID2", ["AAA"], NOW - timedelta(days=100), datetime.max.replace(tzinfo=timezone.utc))
    assert sm.resolve("AAA", NOW - timedelta(days=200)) == "UID1"
    assert sm.resolve("AAA", NOW) == "UID2"
    assert sm.universe(NOW) == ["UID2"]

def test_orthogonalize_rejects_collinear_and_handles_rank_deficient():
    rng = np.random.default_rng(1)
    B = rng.normal(size=(20, 3))
    Q = np.hstack([B, B[:, [0]] * 2.0])  # exactly collinear duplicate column
    a = B[:, 0] * 3.0 + 1e-9 * rng.normal(size=20)
    with pytest.raises(ValueError):
        orthogonalize(a, Q)
    a2 = rng.normal(size=20)
    out = orthogonalize(a2, Q)
    assert abs(float(np.linalg.norm(out)) - 1.0) < 1e-9

def test_dsr_rejects_snooped_and_passes_strong():
    assert deflated_sharpe(2.5, 5000, 500, 0.1, 3.2) < 0.50  # snooped SR dies
    with pytest.raises(ValueError):
        require_dsr(2.5, 5000, 500, 0.1, 3.2)
    assert require_dsr(4.0, 10, 500, 0.0, 3.0) >= 0.99

def test_cpcv_purge_embargo():
    splits = list(cpcv_splits(100, n_partitions=5, n_test=1, embargo_pct=0.05))
    assert len(splits) == 5
    for tr, te in splits:
        assert len(set(tr) & set(te)) == 0
        assert (np.abs(tr[:, None] - te[None, :]).min() >= 5)

def test_pbo_bounds():
    rng = np.random.default_rng(2)
    IS = rng.normal(size=(8, 20)); OOS = rng.normal(size=(8, 20))
    assert 0.0 <= pbo(IS, OOS) <= 1.0

def test_ledoit_wolf_psd_and_shrunk():
    rng = np.random.default_rng(3)
    X = rng.normal(size=(60, 8))
    C, d = ledoit_wolf_shrinkage(X)
    assert 0.0 <= d <= 1.0
    assert np.all(np.linalg.eigvalsh((C + C.T) / 2) > 0)
    assert np.all(np.diag(C) > 0)

def test_evt_var_es_ordering():
    rng = np.random.default_rng(4)
    L = np.abs(rng.normal(0, 1, size=2000)) + 0.05
    v99, es99 = evt_var_es(L, 0.99)
    v999, es999 = evt_var_es(L, 0.999)
    assert 0 < v99 < es99 and v99 < v999  # ES dominates VaR; deeper tail larger

def test_mvo_respects_leverage_and_adv():
    rng = np.random.default_rng(5)
    X = rng.normal(size=(120, 4)); C, _ = ledoit_wolf_shrinkage(X)
    a = np.array([0.1, 0.05, 0.08, 0.02])
    w = mean_variance(a, C, 1.0, lmax=1.0, adv_cap=np.full(4, 0.3))
    assert float(np.abs(w).sum()) <= 1.0 + 1e-9
    assert float(np.abs(w).max()) <= 0.3 + 1e-9

def test_hrp_sums_to_one():
    rng = np.random.default_rng(6)
    X = rng.normal(size=(120, 5)); C, _ = ledoit_wolf_shrinkage(X)
    w = hrp_weights(C)
    assert abs(float(w.sum()) - 1.0) < 1e-9 and bool((w > 0).all())

def test_bs_put_call_parity_and_sabr_atm():
    c = bs_price(100, 100, 1, 0.05, 0.2, "call"); p = bs_price(100, 100, 1, 0.05, 0.2, "put")
    import math
    assert abs((c - p) - (100 - 100 * math.exp(-0.05))) < 1e-9
    iv = sabr_iv(100, 100, 1, alpha=0.2, beta=0.5, rho=-0.3, nu=0.4)
    assert abs(iv - 0.2 / 100**0.5) < 0.01  # Hagan ATM -> alpha / F^(1-beta)

def test_microstructure_and_execution():
    assert ofi_tick(10, 500, 10, 400, 11, 300, 11, 350) == pytest.approx(150.0)
    assert microprice(10, 500.0, 11, 300.0) == pytest.approx((500 * 11 + 300 * 10) / 800)
    with pytest.raises(ValueError):
        microprice(11, 100.0, 10, 100.0)  # crossed
    traj = almgren_chriss(1000.0, 1.0, 11, 0.3, 1e-6, 1e-7, 1e-6)
    assert traj[0] == pytest.approx(1000.0) and traj[-1] == pytest.approx(0.0, abs=1e-6)
    assert bool((np.diff(traj) <= 0).all())
    assert sor_split({"A": 700, "B": 300}, 1000) == {"A": pytest.approx(700), "B": pytest.approx(300)}
    assert sqrt_impact_cost(100, 50.0, 0.02, 1e6, 0.01) > 0.01 * 100  # impact over spread

def test_supervisor_blocks_hallucination_and_hype():
    sup = Supervisor()
    with pytest.raises(ValueError):
        sup.step("h", ToolCall("invent_order", {}), {"x": 1}, True)
    with pytest.raises(ValueError):
        sup.step("guaranteed risk-free profit", ToolCall("solve_hrp_portfolio", {"cov": "c"}), {"w": 1}, True)
    ev = sup.step("test momentum hypothesis", ToolCall("solve_hrp_portfolio", {"cov": "c"}), {"w": 1}, True)
    assert ev.critic_pass
    assert sup.memory[-1].critic_pass and not sup.memory[0].critic_pass  # audit keeps blocked attempts

def test_ledger_recon_and_red_button():
    from decimal import Decimal as D
    L = Ledger()
    L.book_oms("AAPL", D("100")); L.book_broker(Fill("o1", "AAPL", D("100"), D("150"))); L.book_custodian("AAPL", D("100"))
    assert L.reconcile() == {} and len(L.chain) == 3
    L.book_oms("AAPL", D("5"))
    with pytest.raises(ValueError):
        L.reconcile()
    clean = GateState(99, 100, 0.01, 0.05, 0.05, 0.995, False, 0.02, 0.01, 0.05, True, True, True)
    assert red_button(clean) == []
    bad = GateState(100, 99, 0.2, 0.05, 0.5, 0.5, True, 0.5, 0.5, 0.05, False, False, False)
    assert len(red_button(bad)) == 10

def test_reverse_stress_hits_loss_level():
    rng = np.random.default_rng(7)
    X = rng.normal(size=(200, 3)); C, _ = ledoit_wolf_shrinkage(X)
    w = np.array([0.4, 0.4, 0.2])
    r = reverse_stress(w, C, 0.05)
    assert abs(float(w @ r) + 0.05) < 1e-9

def test_adjust_price():
    assert adjust_price(100.0, "split", 2.0) == 50.0
    with pytest.raises(ValueError):
        adjust_price(100.0, "split", 0.0)


def test_registry_n_degrades_snooped_sharpe():
    import tempfile, os
    from delta_omega.registry import TrialRegistry
    p = os.path.join(tempfile.mkdtemp(), "exp.sqlite3")
    r = TrialRegistry(p)
    first = r.record("genuine momentum", 4.0, 500, 0.0, 3.0)
    assert first.verdict == "PASS" and first.n_at_test == 1
    for i in range(200):
        r.record(f"snoop {i}", 2.5, 500, 0.1, 3.2)
    late = r.record("same SR2.5 after snooping", 2.5, 500, 0.1, 3.2)
    assert late.verdict == "REJECT" and late.dsr < first.dsr
    assert r.trial_count() == 202
    assert r.dsr_with_registry(4.0, 500, 0.0, 3.0) < first.dsr  # N grew; bar is higher now
    assert len(r.history()) == 100  # bounded reads
    with pytest.raises(ValueError):
        r.record("   ", 1.0, 100, 0.0, 3.0)
    r.close()
