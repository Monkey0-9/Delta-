from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ExperimentMetrics:
    total_return: float
    annualized_return: float
    volatility: float
    sharpe: float
    sortino: float
    max_drawdown: float

    turnover: float
    transaction_cost: float

    var_95: float
    cvar_95: float

    hit_rate: float
    trade_count: int

    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ExperimentResult:
    experiment_id: str
    experiment_fingerprint: str

    metrics: ExperimentMetrics

    validation_passed: bool
    rejection_reasons: tuple[str, ...] = ()

    artifact_hash: str | None = None