from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal
from simulation.backtest.config import BacktestConfig
from simulation.backtest.engine import BacktestContext
from simulation.costs.model import CostModel
from simulation.replay.event import ReplayEvent


def apply_fill_cost(ctx: BacktestContext, *, price: Decimal, qty: Decimal, cost: CostModel) -> Decimal:
    """Deduct notional + costs from cash, count fill. Returns total charge."""
    charge = price * qty + cost.total_cost(price=price, quantity=qty)
    ctx.cash -= charge
    ctx.fills += 1
    return charge


@dataclass(frozen=True, slots=True)
class TargetOrder:
    instrument: str
    quantity: Decimal
    price: Decimal


class BaseStrategy(ABC):
    """Strategy harness contract: pure signal -> target orders per event."""

    @abstractmethod
    def on_event(self, event: ReplayEvent, ctx: BacktestContext) -> tuple[TargetOrder, ...]:
        ...


class SignalStrategy(BaseStrategy):
    """Threshold signal strategy: BUY when signal > buy_threshold, flat otherwise."""

    def __init__(
        self,
        *,
        signal: tuple[Decimal, ...],
        prices: tuple[Decimal, ...],
        instrument: str = "SYM",
        buy_threshold: Decimal = Decimal("0"),
        size: Decimal = Decimal("1"),
    ) -> None:
        if len(signal) != len(prices) or not signal:
            raise ValueError("signal/prices must align and be non-empty.")
        self._signal = signal
        self._prices = prices
        self._instrument = instrument
        self._threshold = buy_threshold
        self._size = size
        self._cursor = 0

    def on_event(self, event: ReplayEvent, ctx: BacktestContext) -> tuple[TargetOrder, ...]:
        if self._cursor >= len(self._signal):
            return ()
        sig = self._signal[self._cursor]
        price = self._prices[self._cursor]
        self._cursor += 1
        if sig > self._threshold:
            return (TargetOrder(self._instrument, self._size, price),)
        return ()


def run_strategy_backtest(
    *,
    config: BacktestConfig,
    events: tuple[ReplayEvent, ...],
    strategy: BaseStrategy,
    cost: CostModel | None = None,
    risk_check=None,
    max_position: Decimal | None = None,
) -> BacktestContext:
    """Wire strategy + costs + optional risk gate into a deterministic loop.

    ``risk_check(order) -> bool`` vetoes orders (risk never bypassed: vetoed
    orders are skipped, never forced). ``max_position`` caps cumulative fills.
    """
    from simulation.replay.engine import ReplayEngine

    model = cost or CostModel()
    ctx = BacktestContext(cash=config.initial_cash)
    from brokers.simulator.clock import SimulationClock
    from datetime import datetime, timezone

    start = min((e.timestamp for e in events), default=datetime.now(timezone.utc))
    engine = ReplayEngine(clock=SimulationClock(start=start))
    position = Decimal("0")

    def handler(event: ReplayEvent) -> None:
        nonlocal position
        for order in strategy.on_event(event, ctx):
            if risk_check is not None and not risk_check(order):
                continue
            if max_position is not None and position + order.quantity > max_position:
                continue
            if not config.allow_short and position + order.quantity < 0:
                continue
            apply_fill_cost(ctx, price=order.price, qty=order.quantity, cost=model)
            position += order.quantity

    engine.run(events, handler)
    return ctx
