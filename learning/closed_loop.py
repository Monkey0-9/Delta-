"""Closed learning loop (P4) - single production wiring.

  fills -> FailureAttributor.classify -> FailureRecord + Experience
        -> recall at decision time (cited evidence, never permission)
        -> AdaptationGate.evaluate for promotion (offline, explicit)

Memory is evidence, not permission: recall() only surfaces lessons;
it never approves trades or widens risk.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Union
from uuid import uuid4

from learning.adaptation.gate import AdaptationGate, PromotionDecision, ValidationEvidence
from learning.failure_attribution.attributor import FailureAttributor
from memory.experience.experience import Experience
from memory.failures.failure import FailureRecord, FailureType

Numeric = Union[Decimal, float, int, str]

_LESSONS: dict[FailureType, str] = {
    FailureType.NO_FAILURE: "Outcome within tolerance; no adaptation needed.",
    FailureType.MODEL_ERROR: "Prediction missed; re-validate features on chronological OOS before reuse.",
    FailureType.REGIME_ERROR: "Regime misclassified; check regime detector calibration for this state.",
    FailureType.DATA_ERROR: "Bad input data; fix feed/validation before trusting similar signals.",
    FailureType.RISK_ERROR: "Risk bound hit; position sizing, not the signal, decided this outcome.",
    FailureType.EXECUTION_ERROR: "Slippage dominated; prefer passive/VWAP slicing at this participation.",
    FailureType.DECISION_ERROR: "Small-signal error; raise confidence bar or abstain in this regime.",
    FailureType.EVENT_ERROR: "Market event anomaly; wait for volatility settling or expand event filter.",
    FailureType.LIQUIDITY_ERROR: "Insufficient liquidity; reduce size or route to alternative venue.",
    FailureType.PORTFOLIO_ERROR: "Portfolio constraint violated; review allocation limits and correlation matrix.",
    FailureType.UNKNOWN: "Ambiguous outcome; keep quarantined pending review.",
}


def _to_decimal(val: Numeric, default: str = "0") -> Decimal:
    """Safely convert numeric input to Decimal without precision loss."""
    if isinstance(val, Decimal):
        return val
    try:
        return Decimal(str(val))
    except Exception:
        return Decimal(default)


@dataclass
class ClosedLoopLedger:
    """In-memory ledger (durable store plugs in behind add/recall)."""

    failures: list[FailureRecord] = field(default_factory=list)
    experiences: list[Experience] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.experiences)

    def clear(self) -> None:
        """Clear all stored failures and experiences."""
        self.failures.clear()
        self.experiences.clear()

    def get_failures(self) -> tuple[FailureRecord, ...]:
        """Return an immutable snapshot of all recorded failures."""
        return tuple(self.failures)

    def get_experiences(self) -> tuple[Experience, ...]:
        """Return an immutable snapshot of all recorded experiences."""
        return tuple(self.experiences)

    def record_trade_outcome(
        self,
        *,
        decision_id: str | None = None,
        instrument: str = "UNKNOWN",
        horizon: str = "today",
        regime: str = "default",
        expected_return: Numeric = Decimal("0"),
        actual_return: Numeric = Decimal("0"),
        data_valid: bool = True,
        slippage: Numeric = Decimal("0"),
        execution_slippage: Numeric | None = None,
        predicted_regime: str = "",
        realized_regime: str = "",
        risk_breached: bool = False,
        model_version: str = "unknown",
        confidence: Numeric = Decimal("0.5"),
    ) -> tuple[FailureRecord, Experience]:
        # Handle execution_slippage alias
        if execution_slippage is not None:
            slippage = execution_slippage

        # Ensure safe Decimal values
        dec_expected = _to_decimal(expected_return, "0")
        dec_actual = _to_decimal(actual_return, "0")
        dec_slippage = _to_decimal(slippage, "0")
        dec_confidence = _to_decimal(confidence, "0.5")

        # Clamp confidence to [0, 1] as required by FailureRecord
        if dec_confidence < Decimal("0"):
            dec_confidence = Decimal("0")
        elif dec_confidence > Decimal("1"):
            dec_confidence = Decimal("1")

        # Fallbacks for empty identifiers
        clean_decision_id = (decision_id or "").strip()
        if not clean_decision_id:
            clean_decision_id = f"dec_{uuid4().hex[:12]}"

        clean_instrument = (instrument or "").strip() or "UNKNOWN"
        clean_regime = (regime or "").strip() or "default"
        clean_horizon = (horizon or "").strip() or "today"
        clean_model_version = (model_version or "").strip() or "unknown"

        ftype = FailureAttributor().classify(
            expected_return=dec_expected,
            actual_return=dec_actual,
            data_valid=bool(data_valid),
            execution_slippage=dec_slippage,
            predicted_regime=predicted_regime or clean_regime,
            realized_regime=realized_regime or clean_regime,
            risk_breached=bool(risk_breached),
        )
        lesson = _LESSONS.get(ftype, "Ambiguous outcome; keep quarantined pending review.")
        record = FailureRecord(
            decision_id=clean_decision_id,
            failure_type=ftype,
            expected_outcome=dec_expected,
            actual_outcome=dec_actual,
            error_magnitude=abs(dec_expected - dec_actual),
            root_cause=f"{ftype.value}: exp={dec_expected} act={dec_actual}",
            lesson=lesson,
            confidence=dec_confidence,
            model_version=clean_model_version,
            regime=clean_regime,
        )
        exp = Experience(
            decision_id=clean_decision_id,
            instrument=clean_instrument,
            horizon=clean_horizon,
            regime=clean_regime,
            prediction=dec_expected,
            actual=dec_actual,
            lesson=lesson,
            failure_type=ftype.value,
            model_version=clean_model_version,
        )
        self.failures.append(record)
        self.experiences.append(exp)
        return record, exp

    def recall(
        self,
        *,
        instrument: str | None = None,
        regime: str | None = None,
        horizon: str | None = None,
        limit: int = 2,
    ) -> tuple[Experience, ...]:
        """Exact-match-first recall. Evidence only."""
        if limit <= 0:
            return ()

        has_query = any(k is not None for k in (instrument, regime, horizon))

        def score(e: Experience) -> int:
            s = 0
            if instrument is not None and e.instrument == instrument:
                s += 4
            if regime is not None and e.regime == regime:
                s += 2
            if horizon is not None and e.horizon == horizon:
                s += 1
            return s

        if not has_query:
            # When no filters specified, return newest experiences up to limit
            return tuple(reversed(self.experiences))[:limit]

        # Rank by score descending, breaking ties with newest timestamp first
        ranked = sorted(
            self.experiences,
            key=lambda e: (score(e), e.timestamp),
            reverse=True,
        )
        return tuple(r for r in ranked if score(r) > 0)[:limit]

    def recall_failures(
        self,
        *,
        regime: str | None = None,
        failure_type: FailureType | str | None = None,
        limit: int = 2,
    ) -> tuple[FailureRecord, ...]:
        """Recall failure records (evidence only)."""
        if limit <= 0:
            return ()

        has_query = any(k is not None for k in (regime, failure_type))
        if not has_query:
            return tuple(reversed(self.failures))[:limit]

        target_ftype = failure_type.value if isinstance(failure_type, FailureType) else failure_type

        def score(f: FailureRecord) -> int:
            s = 0
            if regime is not None and f.regime == regime:
                s += 2
            if target_ftype is not None and (f.failure_type == target_ftype or f.failure_type.value == target_ftype):
                s += 2
            return s

        ranked = sorted(
            self.failures,
            key=lambda f: (score(f), f.timestamp),
            reverse=True,
        )
        return tuple(r for r in ranked if score(r) > 0)[:limit]


def evaluate_promotion(
    *,
    walk_forward_passed: bool,
    out_of_sample_passed: bool,
    stress_passed: bool,
    regression_passed: bool,
    protected_failures_passed: bool,
) -> PromotionDecision:
    """Canonical promotion gate (AdaptationGate). Offline, explicit."""
    return AdaptationGate().evaluate(
        ValidationEvidence(
            walk_forward_passed=bool(walk_forward_passed),
            out_of_sample_passed=bool(out_of_sample_passed),
            stress_passed=bool(stress_passed),
            regression_passed=bool(regression_passed),
            protected_failures_passed=bool(protected_failures_passed),
        )
    )


__all__ = [
    "ClosedLoopLedger",
    "evaluate_promotion",
    "_LESSONS",
]
