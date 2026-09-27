
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Callable

from simulation.backtest.config import BacktestConfig
from simulation.backtest.result import BacktestResult
from simulation.replay.engine import ReplayEngine
from simulation.replay.event import ReplayEvent


@dataclass(slots=True)
class BacktestContext:
    cash: Decimal
    fills: int = 0
    realized_pnl: Decimal = Decimal("0")
    unrealized_pnl: Decimal = Decimal("0")


class BacktestEngine:
    """
    Deterministic backtest orchestration.

    This class deliberately does not implement:
    - strategy logic
    - portfolio accounting
    - broker execution
    - risk rules

    Those remain independent components.
    """

    def __init__(
        self,
        *,
        config: BacktestConfig,
        replay: ReplayEngine,
    ) -> None:
        self._config = config
        self._replay = replay

    def run(
        self,
        events: tuple[ReplayEvent, ...],
        handler: Callable[
            [ReplayEvent, BacktestContext],
            None,
        ],
    ) -> BacktestResult:
        context = BacktestContext(
            cash=self._config.initial_cash,
        )

        def process(event: ReplayEvent) -> None:
            handler(event, context)

        statistics = self._replay.run(
            events,
            process,
        )

        final_equity = (
            context.cash
            + context.unrealized_pnl
        )

        total_return = (
            final_equity / self._config.initial_cash
        ) - Decimal("1")

        return BacktestResult(
            initial_equity=self._config.initial_cash,
            final_equity=final_equity,
            total_return=total_return,
            realized_pnl=context.realized_pnl,
            unrealized_pnl=context.unrealized_pnl,
            events_processed=statistics.events_processed,
            fills=context.fills,
        )
