"""P1-slice regression: PIT guards, canonical DSR/CPCV-PBO, calibrated
capacity, L3 replay parity. All deterministic; no network."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import numpy as np
import pytest

UTC = timezone.utc


# ---- Group 12: PIT guards ----

def test_pit_lag_fail_closed():
    from research.validation.pit_guards import (
        LeakageError, assert_no_future_bars)
    as_of = datetime(2026, 9, 29, 16, 0, tzinfo=UTC)
    lag = timedelta(minutes=15)
    ok_bars = [as_of - timedelta(minutes=20), as_of - timedelta(minutes=16)]
    assert assert_no_future_bars(ok_bars, as_of, lag) == 2
    with pytest.raises(LeakageError):
        assert_no_future_bars(ok_bars + [as_of - timedelta(minutes=5)],
                              as_of, lag)


def test_pit_embargo_overlap_rejected():
    from research.validation.pit_guards import LeakageError, assert_embargo_ok
    d = lambda h: datetime(2026, 1, 1, tzinfo=UTC) + timedelta(hours=h)  # noqa: E731
    # clean split passes
    assert_embargo_ok(d(0), d(10), d(12), d(20), timedelta(hours=1))
    # overlapping train fails
    with pytest.raises(LeakageError):
        assert_embargo_ok(d(0), d(15), d(12), d(20), timedelta(hours=1))
    # embargo-tail violation fails (train ends inside embargo after test end)
    with pytest.raises(LeakageError):
        assert_embargo_ok(d(0), d(21), d(12), d(20), timedelta(hours=2))


def test_shuffle_placebo_flags_leakage():
    from research.validation.pit_guards import shuffle_placebo_diagnostic
    # shuffled matches IS -> suspect
    r = shuffle_placebo_diagnostic(0.05, [0.05, 0.06, 0.04])
    assert r["leak_suspect"] is True
    # shuffled ~ zero while IS strong -> clean
    r2 = shuffle_placebo_diagnostic(0.05, [0.001, -0.002, 0.0])
    assert r2["leak_suspect"] is False


def test_dataset_manifest_link_verify():
    from research.validation.pit_guards import link_dataset_manifest
    m = link_dataset_manifest(
        dataset_fingerprint="DS-ABC123", code_sha="deadbeef",
        feature_version="feat-v3", params={"w": 5}, seed=7,
        train_period="2014-2021", validation_period="2022-2023",
        oos_period="2024-2026")
    assert m.verify() is True
    assert m.manifest_hash.startswith("MAN-")
    with pytest.raises(Exception):
        link_dataset_manifest(dataset_fingerprint="", code_sha="x",
                              feature_version="v", params={}, seed=1,
                              train_period="a", validation_period="b",
                              oos_period="c")


# ---- Group 22: canonical DSR / PBO ----

def test_canonical_dsr_kills_snooped_sharpe():
    from research.statistics.canonical import deflated_sharpe
    assert deflated_sharpe(2.5, 5000, 500, 0.1, 3.2) < 0.50
    assert 0.0 <= deflated_sharpe(2.0, 10, 252, 0.0, 3.0) <= 1.0


def test_factory_and_stats_delegate_to_canonical():
    from research.alpha_factory_v2 import deflated_sharpe as f_dsr
    from research.real_loop.alpha_stats import deflated_sharpe as s_dsr
    from research.statistics.canonical import deflated_sharpe as c_dsr
    assert f_dsr(2.0, 10, 252) == pytest.approx(c_dsr(2.0, 10, 252, 0.0, 3.0))
    assert s_dsr(1.5, 20) == pytest.approx(c_dsr(1.5, 20, 252, 0.0, 3.0))


def test_cpcv_pbo_separates_signal_from_noise():
    from research.statistics.canonical import cpcv_pbo
    rng = np.random.default_rng(7)
    t, n = 600, 6
    # one persistent edge + noise trials -> low PBO
    edge = rng.normal(0.002, 0.01, t)
    panel_edge = np.column_stack([edge + rng.normal(0, 0.01, t) for _ in range(n)])
    r_edge = cpcv_pbo(panel_edge)
    assert r_edge["method"] == "ldp-cpcv-pbo" and r_edge["n_splits"] > 2
    # pure noise panel -> high PBO (no persistent winner)
    panel_noise = rng.normal(0, 0.01, (t, n))
    r_noise = cpcv_pbo(panel_noise)
    assert 0.0 <= r_noise["pbo"] <= 1.0
    assert r_edge["pbo"] <= r_noise["pbo"]


def test_single_split_fallback_honest_labels():
    from research.statistics.canonical import pbo_single_split
    r = pbo_single_split([1.0, 2.0], [0.5, -0.5])
    assert r["pbo"] == 1.0 and r["method"] == "single-split-rank-fallback"
    r2 = pbo_single_split([1.0, 2.0], [0.5, 3.0])
    assert r2["pbo"] == 0.0


# ---- Group 23: calibrated capacity ----

def test_fit_gamma_recovers_true_impact():
    from research.capacity.calibrated import (
        SIGMA_PROXY_BPS, capacity_curve, fit_gamma, max_capacity)
    rng = np.random.default_rng(11)
    true_gamma = 0.7
    fills = []
    for p in np.linspace(0.001, 0.05, 12):
        cost = true_gamma * SIGMA_PROXY_BPS * float(np.sqrt(p))
        fills.append((float(p), cost + float(rng.normal(0, 0.05))))
    cal = fit_gamma(fills)
    assert cal.calibrated is True
    assert abs(cal.gamma - true_gamma) < 0.1
    assert cal.r_squared > 0.9
    curve = capacity_curve(30.0, 1e7, 100.0, calibration=cal)
    assert all(p.calibration_source == cal.source for p in curve)
    # proxy path is explicitly labeled uncalibrated
    proxy = capacity_curve(30.0, 1e7, 100.0)
    assert all(p.calibration_source == "proxy-uncalibrated" for p in proxy)
    mc = max_capacity(30.0, adv_shares=1e7, price=100.0, calibration=cal)
    assert mc["calibrated"] is True and mc["capital_usd"] > 0
    with pytest.raises(ValueError):
        fit_gamma([(0.01, 5.0)])  # fail-closed: no silent proxy


def test_factory_capacity_gate_labels_source():
    from research.alpha_factory_v2 import AlphaFactoryV2, HypothesisV2
    import math
    f = AlphaFactoryV2()
    strong_is = [[0.01 + 0.002 * ((i + t) % 3 - 1) for t in range(120)] for i in range(4)]
    strong_oos = [0.008 + 0.002 * ((t * 7) % 5 - 2) / 5 for t in range(252)]
    res = f.run(HypothesisV2("H-S", "drift", "mom", trials_context=1),
                returns_is=strong_is, returns_oos=strong_oos,
                cost_bps_per_trade=0.5, min_oos_sharpe=0.1, min_dsr=0.5,
                experiment_seq=99)
    gates = {g.gate: g for g in res.gates}
    assert "proxy-uncalibrated" in gates["capacity"].detail
    assert "single-split" in gates["pbo"].detail


# ---- Group 16: replay parity ----

def _script():
    from simulation.l3_engine import L3Event
    D = Decimal
    return [
        L3Event(1, 1, "ADD", "a", "buy", D("100"), D("10")),
        L3Event(2, 2, "ADD", "b", "buy", D("100"), D("10")),
        L3Event(3, 3, "ADD", "c", "buy", D("100"), D("10")),
        L3Event(4, 4, "ADD", "s1", "sell", D("101"), D("5")),
        L3Event(5, 5, "MARKET", "t1", "buy", D("0"), D("3")),
    ]


def test_replay_determinism_and_ordering():
    from simulation.replay.parity import check_determinism, check_ordering
    ev = _script()
    assert check_determinism(ev)["passed"] is True
    assert check_ordering(ev)["passed"] is True


def test_replay_policy_divergence_documented():
    from simulation.replay.parity import check_replace_policy_divergence
    r = check_replace_policy_divergence()
    assert r["passed"] is True
    assert r["retain_position"] == 1 and r["lose_position"] == 2


def test_replay_no_crossed_book():
    from simulation.replay.parity import check_no_crossed_book, replay
    book, _ = replay(_script())
    assert check_no_crossed_book(book)["passed"] is True
