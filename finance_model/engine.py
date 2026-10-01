"""Deterministic financial-analysis policy adapter (NOT an LLM / model).

This module was previously named ``FinanceModel``; that name was
misleading. It performs no inference — it maps caller-supplied
(expected_return, uncertainty) inputs onto a candidate action via fixed
thresholds. Real model inference lives in the model gateway / inference
stack; forecasts in forecast models; risk in the risk engine.
"""
from __future__ import annotations

import warnings
from decimal import Decimal

from .contracts import (
    FinancialAnalysis,
    FinancialAnalysisInput,
)


class FinanceAnalysisPolicy:
    """
    Deterministic policy adapter: uncertainty -> confidence,
    confidence/expected-return -> candidate action.

    IMPORTANT:
    This component performs no model inference, has no broker access,
    and cannot execute orders. Candidate actions require downstream
    risk-firewall approval and OMS lifecycle.
    """

    def __init__(self, model_version: str) -> None:
        if not model_version:
            raise ValueError("model_version cannot be empty.")

        self._model_version = model_version

    def analyze(
        self,
        request: FinancialAnalysisInput,
    ) -> FinancialAnalysis:

        uncertainty = request.uncertainty

        confidence = max(
            Decimal("0"),
            min(
                Decimal("1"),
                Decimal("1") - uncertainty,
            ),
        )

        if confidence < Decimal("0.40"):
            candidate_action = "WAIT"

        elif request.expected_return > Decimal("0"):
            candidate_action = "BUY_CANDIDATE"

        elif request.expected_return < Decimal("0"):
            candidate_action = "REDUCE_CANDIDATE"

        else:
            candidate_action = "HOLD"

        risks = (
            "model uncertainty",
            "regime uncertainty",
            "market uncertainty",
            "execution uncertainty",
        )

        uncertainty_sources = (
            "forecast uncertainty",
            "regime uncertainty",
            "data uncertainty",
        )

        thesis = (
            f"{request.instrument} has a model-implied expected return "
            f"of {request.expected_return}. "
            f"The candidate action is {candidate_action}, "
            f"subject to risk and execution controls."
        )

        scenario = (
            request.stress_summary
            if request.stress_summary
            else "No stress scenario supplied."
        )

        return FinancialAnalysis(
            instrument=request.instrument,
            thesis=thesis,
            horizon=request.horizon,
            expected_return=request.expected_return,
            confidence=confidence,
            risks=risks,
            uncertainty_sources=uncertainty_sources,
            evidence=request.evidence,
            scenario_analysis=scenario,
            candidate_action=candidate_action,
            invalidating_conditions=(
                "material regime change",
                "forecast deterioration",
                "risk-limit breach",
                "data-quality failure",
                "liquidity deterioration",
            ),
            model_version=self._model_version,
        )


def __getattr__(name: str):
    # Backward-compat alias: FinanceModel -> FinanceAnalysisPolicy.
    if name == "FinanceModel":
        warnings.warn(
            "FinanceModel is renamed FinanceAnalysisPolicy (deterministic "
            "policy adapter, not a model). Update imports.",
            DeprecationWarning,
            stacklevel=2,
        )
        return FinanceAnalysisPolicy
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")