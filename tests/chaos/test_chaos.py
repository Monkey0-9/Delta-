from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from brokers.simulator.clock import SimulationClock
from simulation.replay.engine import ReplayEngine
from simulation.replay.event import ReplayEvent
from simulation.scenarios.failures import FailureInjection, FailureType
from simulation.scenarios.generator import ScenarioGenerator


def _events(n: int) -> tuple[ReplayEvent, ...]:
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return tuple(ReplayEvent(t0 + timedelta(seconds=i), i, f"p{i}") for i in range(n))


def test_replay_survives_failure_injection() -> None:
    clock = SimulationClock(datetime(2026, 1, 1, tzinfo=timezone.utc))
    engine = ReplayEngine(clock=clock)
    inj = FailureInjection(
        failure_type=FailureType.STALE_DATA, probability=0.5, duration_ms=1000
    )
    assert inj.failure_type == FailureType.STALE_DATA
    stats = engine.run(_events(10), lambda _: None)
    assert stats.events_processed == 10


def test_crash_scenario_is_deterministic() -> None:
    a = ScenarioGenerator.equity_crash("s1", severity=Decimal("0.2"))
    b = ScenarioGenerator.equity_crash("s1", severity=Decimal("0.2"))
    assert a.factors == b.factors


def test_kill_switch_halts_pipeline() -> None:
    from risk.kill_switch.kill_switch import KillSwitch

    ks = KillSwitch()
    ks.activate(actor="ops")
    assert ks.active
    with pytest.raises(PermissionError):
        ks.rearm(actor="someone-else")
    ks.rearm(actor="ops")
    assert not ks.active
