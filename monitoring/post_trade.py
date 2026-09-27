from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ExecutionObservation:
    order_id: str
    decision_price: float
    average_fill_price: float
    benchmark_price: float
    quantity: float


@dataclass(frozen=True)
class ExecutionAnalytics:
    order_id: str
    implementation_shortfall_bps: float
    benchmark_slippage_bps: float
    absolute_slippage: float


def analyze(
    observation: ExecutionObservation,
) -> ExecutionAnalytics:

    if observation.decision_price <= 0:
        raise ValueError(
            "decision price must be positive"
        )

    if observation.benchmark_price <= 0:
        raise ValueError(
            "benchmark price must be positive"
        )

    is_bps = (
        (
            observation.average_fill_price
            - observation.decision_price
        )
        / observation.decision_price
    ) * 10_000

    benchmark_bps = (
        (
            observation.average_fill_price
            - observation.benchmark_price
        )
        / observation.benchmark_price
    ) * 10_000

    slippage = (
        abs(
            observation.average_fill_price
            - observation.decision_price
        )
        * observation.quantity
    )

    return ExecutionAnalytics(
        order_id=observation.order_id,
        implementation_shortfall_bps=is_bps,
        benchmark_slippage_bps=benchmark_bps,
        absolute_slippage=slippage,
    )