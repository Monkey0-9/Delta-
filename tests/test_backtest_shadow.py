"""Item 12 + item 7 gates: backtester-microstructure wiring + shadow runner."""
from __future__ import annotations

from decimal import Decimal


def test_backtest_engine_routes_through_microstructure():
    import delta_compat  # noqa
    from simulation.backtest.config import BacktestConfig
    from simulation.backtest.engine import BacktestEngine
    from simulation.replay.engine import ReplayEngine
    from brokers.simulator.clock import SimulationClock
    from datetime import datetime, timezone

    engine = BacktestEngine(config=BacktestConfig(initial_cash=Decimal("1000000")),
                            replay=ReplayEngine(clock=SimulationClock(datetime.now(timezone.utc))))
    signals = ((1_000_000, "buy", Decimal("100.00"), Decimal("10")),
               (2_000_000, "sell", Decimal("100.00"), Decimal("10")))
    r1 = engine.run_with_microstructure(signals, seed=7)
    r2 = engine.run_with_microstructure(signals, seed=7)
    assert r1.fills == r2.fills and r1.final_equity == r2.final_equity  # deterministic
    assert r1.fills > 0 and r1.events_processed == 2
    import pytest
    with pytest.raises(ValueError):
        engine.run_with_microstructure(((1, "hold", Decimal("1"), Decimal("1")),), seed=7)
    with pytest.raises(ValueError):
        engine.run_with_microstructure(((1, "buy", Decimal("1"), Decimal("0")),), seed=7)


def test_shadow_runner_promotion_gates():
    from deployment.shadow import ShadowRunner, ShadowDecision
    runner = ShadowRunner()
    assert runner.evaluate("ghost")["observations"] == 0
    assert runner.promotion_decision("ghost")["decision"] == "HOLD"
    for i in range(30):
        runner.record(ShadowDecision("strat", "BUY", 10.0, "BUY", 5.0))
    d = runner.promotion_decision("strat")
    assert d["decision"] == "PROMOTE" and d["observations"] == 30
    runner2 = ShadowRunner()
    for i in range(30):
        runner2.record(ShadowDecision("loser", "BUY", 10.0, "BUY", -50.0))
    assert runner2.promotion_decision("loser", max_allowed_loss=10.0)["decision"] == "REJECT"
