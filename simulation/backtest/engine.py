
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Callable

from simulation.backtest.config import BacktestConfig
from simulation.backtest.result import BacktestResult
from simulation.replay.engine import ReplayEngine
from simulation.replay.event import ReplayEvent

# ---------------------------------------------------------------------------
# Step 1.1 bridge: execution pricing wired to the delta_omega math kernel.
# Single price source per scan: delta_omega.portfolio_exec is the authority
# for sqrt transient impact; this module only adapts its output to fills.
# Provenance label: src="delta_omega:sqrt_transient_impact|AC-trajectory".
# ---------------------------------------------------------------------------
PRICE_SOURCE = "delta_omega:sqrt_transient_impact"


def execution_price_with_impact(
    mid: float,
    side: str,
    qty_shares: float,
    sigma: float,
    market_volume_shares: float,
    spread: float,
    gamma: float = 0.5,
) -> tuple[float, str]:
    """Fill price via the kernel: P_fill = P_mid +/- (spread/2 + g*s*sqrt(q/V)).

    Returns (price, src_label). Fail-closed on bad inputs (raises).
    """
    from delta_omega.portfolio_exec import execution_price

    return execution_price(mid, side, qty_shares, sigma, market_volume_shares, spread, gamma), PRICE_SOURCE


def order_needs_slicing(order_qty: float, market_volume: float, threshold: float = 0.10) -> bool:
    """True when V_order > threshold * V_market (default 10% ADV rule)."""
    from delta_omega.portfolio_exec import AlmgrenChrissTrajectory

    return AlmgrenChrissTrajectory.needs_slicing(order_qty, market_volume, threshold)


def slice_order_ac(
    n_shares: float,
    T: float,
    n_steps: int,
    sigma: float,
    eta: float,
    gamma_: float,
    lam_risk: float,
) -> tuple[list[float], str]:
    """AC-optimal inventory trajectory slices for oversized orders.

    Returns (per-slice child quantities, src_label).
    """
    from delta_omega.portfolio_exec import AlmgrenChrissTrajectory

    traj = AlmgrenChrissTrajectory(n_shares, T, n_steps, sigma, eta, gamma_, lam_risk).trajectory
    slices = [float(d) for d in (-__import__("numpy").diff(traj, prepend=n_shares))]
    return slices, "delta_omega:almgren_chriss"


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

    def run_with_microstructure(
        self,
        signals: tuple[tuple[int, str, Decimal, Decimal], ...],
        *,
        seed: int = 7,
        vol_20d: float = 0.02,
    ) -> BacktestResult:
        """Route orders through the deterministic microstructure engine.

        Each signal is (event_ns, side["buy"|"sell"], limit_price|None, quantity).
        Limit price None = market (collared). Book is seeded per-bar from the
        signal price with vol-scaled spread; fills settle cash/position with
        fees inside SimEngine. Deterministic: same signals+seed -> same result.
        """
        from research.real_loop.market_sim import SimEngine

        engine = SimEngine(seed=seed)
        try:
            for i, (event_ns, side, price, qty) in enumerate(signals):
                if side not in ("buy", "sell"):
                    raise ValueError(f"signal {i}: side must be buy|sell.")
                if qty <= 0:
                    raise ValueError(f"signal {i}: quantity must be positive.")
                ref = price if price is not None else Decimal("100")
                engine.build_book_from_bar(ref, vol_20d)
                engine.submit(f"bt-{i}", side, price, qty)
                engine.step_until(event_ns, ref)
            mark_px = signals[-1][2] if signals and signals[-1][2] is not None else Decimal("100")
            state = engine.mark(Decimal(mark_px))
            final_equity = state["equity"]
            total_return = (final_equity / self._config.initial_cash) - Decimal("1")
            return BacktestResult(
                initial_equity=self._config.initial_cash,
                final_equity=final_equity,
                total_return=total_return,
                realized_pnl=final_equity - self._config.initial_cash,
                unrealized_pnl=Decimal("0"),
                events_processed=len(signals),
                fills=state["n_fills"],
            )
        finally:
            engine.close()
