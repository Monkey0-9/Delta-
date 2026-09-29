"""Validation package for strategy promotion gates."""

from .advanced_metrics import (
    rank_ic,
    icir,
    deflated_sharpe_ratio,
    probability_backtest_overfitting,
    newey_west_tstat,
    bonferroni_holm,
)
from .validation_gates import GateResult, ValidationGateParameters, ValidationGate

__all__ = [
    "rank_ic",
    "icir",
    "deflated_sharpe_ratio",
    "probability_backtest_overfitting",
    "newey_west_tstat",
    "bonferroni_holm",
    "GateResult",
    "ValidationGateParameters",
    "ValidationGate",
]
