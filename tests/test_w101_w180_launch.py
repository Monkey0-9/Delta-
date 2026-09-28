"""W101-W180 launch gate: one fast test proving the full slice works."""
from __future__ import annotations

from decimal import Decimal

import numpy as np


def test_canonical_schemas_have_l1_l2_l3_and_pit():
    from schemas.events import L1Delta, L2Delta, L3OrderEvent, PITStamps, Quote
    from core.domain.timestamp import utc_now
    from datetime import timedelta
    now = utc_now()
    stamps = PITStamps(as_of=now, publication_time=now - timedelta(seconds=2),
                       ingestion_time=now - timedelta(seconds=1),
                       observation_time=now - timedelta(seconds=3))
    assert stamps.is_usable(now)
    assert L1Delta(symbol="SPY", seq=1, stamps=stamps).schema_version == 2
    assert L2Delta(symbol="SPY", side="BID", seq=1).schema_version == 2
    assert L3OrderEvent(symbol="SPY", action="ADD", order_id="o1").schema_version == 2
    assert Quote(symbol="SPY").schema_version == 2


def test_l2_engine_deterministic_replay_and_lifecycle():
    from simulation.l2_engine import L2Engine
    def run():
        e = L2Engine(seed=7)
        e.add("a1", "buy", Decimal("100.00"), Decimal("50"), latency_ns=50_000)
        e.add("b1", "sell", Decimal("100.00"), Decimal("30"), latency_ns=50_000)
        e.step_until(10_000_000)
        assert e.queue_position("a1") == 0  # resting remainder at front
        assert e.replace("a1", Decimal("99.99"), Decimal("20"))
        assert e.cancel("a1") is True
        assert e.cancel("nope") is False
        return [(f.buy_id, f.sell_id, f.price, f.quantity) for f in e.fills]
    assert run() == run()  # seed -> identical replay
    assert len(run()) == 1


def test_queue_hidden_priority_and_partial_fills():
    from simulation.l2_engine import L2Engine
    e = L2Engine(seed=3)
    e.add("vis", "buy", Decimal("100.00"), Decimal("10"), latency_ns=0)
    e.add("hid", "buy", Decimal("100.00"), Decimal("10"), hidden=True, latency_ns=0)
    e.add("take", "sell", Decimal("100.00"), Decimal("15"), latency_ns=0)
    e.step_until(10_000_000)
    fills = e.fills
    assert sum(f.quantity for f in fills) == Decimal("15")
    # visible resting order must be maker before hidden at same price
    assert fills[0].maker_id == "vis"


def test_execution_wiring_spread_impact_report():
    from execution.paper.broker import PaperBroker
    from execution.ems.adapter import ExecutionRequest
    b = PaperBroker({"SPY": 100.0}, spreads_bps={"SPY": 5.0}, adv={"SPY": 1_000_000.0})
    ack = b.submit(ExecutionRequest("o-launch", "SPY", 100.0))
    assert ack.accepted
    rep = b.execution_report("o-launch")
    assert rep["exec_model_version"] == "exec-sim-v1"
    assert rep["participation_rate"] > 0
    assert "total_impact_bps" in rep["impact_bps"]


def test_kalman_transition_and_conditioning():
    from quant.regime.kalman import (KalmanFilter1D, estimate_transition_matrix,
                                     forecast_distribution, persistence,
                                     regime_uncertainty, regime_conditioned_weights)
    kf = KalmanFilter1D()
    levels, variances = kf.filter_series(np.array([0.01, 0.02, -0.01, 0.015]))
    assert len(levels) == 4 and all(v > 0 for v in variances)
    states = np.array([0, 0, 1, 1, 2, 1, 0])
    t = estimate_transition_matrix(states, 3)
    assert np.allclose(t.sum(axis=1), 1.0)
    assert all(0 <= p <= 1 for p in persistence(t))
    dist = forecast_distribution(t, np.array([1.0, 0.0, 0.0]), steps=2)
    assert abs(dist.sum() - 1.0) < 1e-9
    assert 0 <= regime_uncertainty(dist) <= 1
    w = regime_conditioned_weights(np.array([0.1, 0.2, 0.3]), dist)
    assert len(w) == 3


def test_historical_scenarios_and_registry_gates():
    from data.scenarios.historical import SCENARIOS, get
    assert len(SCENARIOS) >= 6
    assert get("HIST-2020-COVID").interval.startswith("2019")
    from research.experiments.registry import Experiment, ExperimentRegistry
    reg = ExperimentRegistry()
    exp = Experiment("EXP-LAUNCH-001", "sha:2020-covid-v1", "abc123", "m-v1", "s-v1",
                     "SPY/QQQ", "2020-01-01 -> 2020-12-31", "spread+impact+latency-v1",
                     feature_version="f-v1", parameter_version="p-v1", seed=7,
                     train_interval="2015 -> 2019", validation_interval="2019",
                     oos_interval="2020", execution_model="exec-sim-v1", benchmark="SPY")
    reg.register(exp)
    bundle = reg.get("EXP-LAUNCH-001").evidence_bundle()
    assert bundle["seed"] == 7 and bundle["state"] == "RESEARCH"
    reg.promote("EXP-LAUNCH-001", "VALIDATED")
    assert reg.get("EXP-LAUNCH-001").state == "VALIDATED"
    try:
        reg.promote("EXP-LAUNCH-001", "PROD")  # must go via PAPER/SHADOW
        raise AssertionError("illegal promotion allowed")
    except ValueError:
        pass
