
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from brokers.simulator.clock import SimulationClock
from simulation.backtest.config import BacktestConfig
from simulation.backtest.engine import BacktestEngine
from simulation.replay.engine import ReplayEngine
from simulation.replay.event import (
    ReplayEvent,
    sort_replay_events,
)


def make_time(seconds: int) -> datetime:
    return (
        datetime(
            2026,
            1,
            1,
            tzinfo=timezone.utc,
        )
        + timedelta(seconds=seconds)
    )


def test_replay_events_are_deterministically_sorted() -> None:
    events = (
        ReplayEvent(
            timestamp=make_time(10),
            sequence=2,
            payload="B",
        ),
        ReplayEvent(
            timestamp=make_time(10),
            sequence=1,
            payload="A",
        ),
        ReplayEvent(
            timestamp=make_time(5),
            sequence=0,
            payload="C",
        ),
    )

    ordered = sort_replay_events(events)

    assert [event.payload for event in ordered] == [
        "C",
        "A",
        "B",
    ]


def test_replay_advances_simulation_clock() -> None:
    clock = SimulationClock(make_time(0))
    engine = ReplayEngine(clock=clock)

    events = (
        ReplayEvent(
            timestamp=make_time(10),
            sequence=0,
            payload="event",
        ),
    )

    received: list[ReplayEvent] = []

    statistics = engine.run(
        events,
        received.append,
    )

    assert len(received) == 1
    assert clock.now == make_time(10)
    assert statistics.events_processed == 1


def test_empty_replay() -> None:
    clock = SimulationClock(make_time(0))
    engine = ReplayEngine(clock=clock)

    result = engine.run(
        (),
        lambda _: None,
    )

    assert result.events_processed == 0
    assert result.start_time is None
    assert result.end_time is None


def test_backtest_initial_equity() -> None:
    clock = SimulationClock(make_time(0))

    engine = BacktestEngine(
        config=BacktestConfig(
            initial_cash=Decimal("100000"),
        ),
        replay=ReplayEngine(clock=clock),
    )

    result = engine.run(
        (),
        lambda _, context: None,
    )

    assert result.initial_equity == Decimal("100000")
    assert result.final_equity == Decimal("100000")
    assert result.total_return == Decimal("0")


def test_backtest_processes_events() -> None:
    clock = SimulationClock(make_time(0))

    engine = BacktestEngine(
        config=BacktestConfig(
            initial_cash=Decimal("100000"),
        ),
        replay=ReplayEngine(clock=clock),
    )

    events = (
        ReplayEvent(
            timestamp=make_time(1),
            sequence=0,
            payload="A",
        ),
        ReplayEvent(
            timestamp=make_time(2),
            sequence=1,
            payload="B",
        ),
    )

    def handler(event: ReplayEvent, context) -> None:
        context.cash -= Decimal("100")

    result = engine.run(
        events,
        handler,
    )

    assert result.events_processed == 2
    assert result.final_equity == Decimal("99800")
    assert result.total_return == Decimal("-0.002")


def test_replay_rejects_time_travel() -> None:
    clock = SimulationClock(make_time(10))
    engine = ReplayEngine(clock=clock)

    events = (
        ReplayEvent(
            timestamp=make_time(5),
            sequence=0,
            payload="invalid",
        ),
    )

    with pytest.raises(ValueError):
        engine.run(
            events,
            lambda _: None,
        )
