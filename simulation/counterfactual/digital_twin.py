from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Callable, Generic, TypeVar


State = TypeVar("State")


@dataclass(frozen=True, slots=True)
class ScenarioOutcome:
    scenario_id: str
    terminal_value: Decimal
    pnl: Decimal
    max_drawdown: Decimal


class DigitalTwin(Generic[State]):

    def __init__(
        self,
        simulator: Callable[
            [State, dict[str, Decimal]],
            ScenarioOutcome,
        ],
    ) -> None:
        self._simulator = simulator

    def simulate(
        self,
        state: State,
        scenarios: tuple[dict[str, Decimal], ...],
    ) -> tuple[ScenarioOutcome, ...]:

        return tuple(
            self._simulator(state, scenario)
            for scenario in scenarios
        )