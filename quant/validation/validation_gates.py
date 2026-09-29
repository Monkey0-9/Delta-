"""Validation gates for strategy promotion."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Any, Optional
import numpy as np

from .advanced_metrics import (
    deflated_sharpe_ratio,
    probability_backtest_overfitting,
    icir,
)


@dataclass(frozen=True, slots=True)
class GateResult:
    """Outcome of a single validation gate."""
    name: str
    passed: bool
    value: float
    threshold: float
    message: str = ""


@dataclass(frozen=True, slots=True)
class ValidationGateParameters:
    """Thresholds for validation gates."""
    min_sharpe: float = 1.0
    min_dsr: float = 0.95
    max_pbo: float = 0.5
    min_icir: float = 0.5
    n_trials: int = 100


class ValidationGate:
    """Promotion gates: Sharpe/DSR, PBO, and ICIR checks."""

    def __init__(self, params: Optional[ValidationGateParameters] = None) -> None:
        self._params = params or ValidationGateParameters()

    def check_sharpe(self, sharpe: float, n_trials: Optional[int] = None) -> GateResult:
        """Pass if raw Sharpe >= min_sharpe and DSR >= min_dsr."""
        trials = n_trials if n_trials is not None else self._params.n_trials
        dsr = deflated_sharpe_ratio(float(sharpe), trials)
        passed = (sharpe >= self._params.min_sharpe) and (dsr >= self._params.min_dsr)
        return GateResult(
            name="sharpe",
            passed=bool(passed),
            value=float(dsr),
            threshold=float(self._params.min_dsr),
            message=f"sharpe={sharpe:.3f} dsr={dsr:.3f} trials={trials}",
        )

    def check_pbo(self, returns_matrix: np.ndarray) -> GateResult:
        """Pass if simplified PBO <= max_pbo."""
        pbo = probability_backtest_overfitting(returns_matrix)
        return GateResult(
            name="pbo",
            passed=bool(pbo <= self._params.max_pbo),
            value=float(pbo),
            threshold=float(self._params.max_pbo),
            message=f"pbo={pbo:.3f}",
        )

    def check_icir(self, signal: np.ndarray, forward_returns: np.ndarray) -> GateResult:
        """Pass if ICIR >= min_icir."""
        value = icir(signal, forward_returns)
        return GateResult(
            name="icir",
            passed=bool(value >= self._params.min_icir),
            value=float(value),
            threshold=float(self._params.min_icir),
            message=f"icir={value:.3f}",
        )

    def validate_all(
        self,
        sharpe: float,
        returns_matrix: np.ndarray,
        signal: np.ndarray,
        forward_returns: np.ndarray,
    ) -> Dict[str, Any]:
        """Run all gates; returns pass/fail dict with details."""
        results = [
            self.check_sharpe(sharpe),
            self.check_pbo(returns_matrix),
            self.check_icir(signal, forward_returns),
        ]
        passed = all(r.passed for r in results)
        return {
            "passed": passed,
            "results": {r.name: r for r in results},
            "summary": {r.name: {"passed": r.passed, "value": r.value,
                                 "threshold": r.threshold, "message": r.message}
                        for r in results},
        }


__all__ = ["GateResult", "ValidationGateParameters", "ValidationGate"]
