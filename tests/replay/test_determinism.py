"""Replay determinism: multi-run bit-identical + ordering + time-travel reject."""
from datetime import datetime, timedelta, timezone

from brokers.simulator.clock import SimulationClock
from simulation.replay.engine import ReplayEngine
from simulation.replay.event import ReplayEvent


def _events(n=25):
    t0 = datetime(2024, 1, 2, 9, 30, tzinfo=timezone.utc)
    # deliberately out of order to prove deterministic sorting
    return tuple(
        ReplayEvent(timestamp=t0 + timedelta(seconds=i * 60), sequence=i, payload={"i": i})
        for i in reversed(range(n))
    )


def _run(n=25):
    eng = ReplayEngine(clock=SimulationClock(datetime(2024, 1, 2, 9, 30, tzinfo=timezone.utc)))
    seen: list[int] = []
    stats = eng.run(_events(n), seen.append if False else lambda e: seen.append(e.sequence))
    return stats, tuple(seen)


def test_replay_bit_identical_across_runs():
    s1, seen1 = _run()
    s2, seen2 = _run()
    assert (s1.events_processed, s1.start_time, s1.end_time) == (
        s2.events_processed, s2.start_time, s2.end_time,
    )
    assert seen1 == seen2 == tuple(range(25))


def test_replay_rejects_time_travel():
    eng = ReplayEngine(clock=SimulationClock(datetime(2024, 1, 2, 10, 30, tzinfo=timezone.utc)))
    try:
        eng.run(_events(5), lambda e: None)
    except ValueError as exc:
        assert "before simulation clock" in str(exc)
    else:
        raise AssertionError("expected time-travel reject")
