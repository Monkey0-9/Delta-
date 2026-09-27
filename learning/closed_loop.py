"""Closed learning loop (P4) - single production wiring.

  fills -> FailureAttributor.classify -> FailureRecord + Experience
        -> recall at decision time (cited evidence, never permission)
        -> AdaptationGate.evaluate for promotion (offline, explicit)

Memory is evidence, not permission: recall() only surfaces lessons;
it never approves trades or widens risk.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from learning.adaptation.gate import AdaptationGate, PromotionDecision, ValidationEvidence
from learning.failure_attribution.attributor import FailureAttributor
from memory.experience.experience import Experience
from memory.failures.failure import FailureRecord, FailureType

_LESSONS: dict[FailureType, str] = {
    FailureType.NO_FAILURE: "Outcome within tolerance; no adaptation needed.",
    FailureType.MODEL_ERROR: "Prediction missed; re-validate features on chronological OOS before reuse.",
    FailureType.REGIME_ERROR: "Regime misclassified; check regime detector calibration for this state.",
    FailureType.DATA_ERROR: "Bad input data; fix feed/validation before trusting similar signals.",
    FailureType.RISK_ERROR: "Risk bound hit; position sizing, not the signal, decided this outcome.",
    FailureType.EXECUTION_ERROR: "Slippage dominated; prefer passive/VWAP slicing at this participation.",
    FailureType.DECISION_ERROR: "Small-signal error; raise confidence bar or abstain in this regime.",
}


@dataclass
class ClosedLoopLedger:
    """In-memory ledger (durable store plugs in behind add/recall)."""

    failures: list[FailureRecord] = field(default_factory=list)
    experiences: list[Experience] = field(default_factory=list)

    def record_trade_outcome(
        self,
        *,
        decision_id: str,
        instrument: str,
        horizon: str,
        regime: str,
        expected_return: Decimal,
        actual_return: Decimal,
        data_valid: bool = True,
        slippage: Decimal = Decimal("0"),
        predicted_regime: str = "",
        realized_regime: str = "",
        risk_breached: bool = False,
        model_version: str = "unknown",
    ) -> tuple[FailureRecord, Experience]:
        ftype = FailureAttributor().classify(
            expected_return=expected_return,
            actual_return=actual_return,
            data_valid=data_valid,
            execution_slippage=slippage,
            predicted_regime=predicted_regime or regime,
            realized_regime=realized_regime or regime,
            risk_breached=risk_breached,
        )
        lesson = _LESSONS.get(ftype, "Ambiguous outcome; keep quarantined pending review.")
        record = FailureRecord(
            decision_id=decision_id,
            failure_type=ftype,
            expected_outcome=expected_return,
            actual_outcome=actual_return,
            error_magnitude=abs(expected_return - actual_return),
            root_cause=f"{ftype.value}: exp={expected_return} act={actual_return}",
            lesson=lesson,
            confidence=Decimal("0.5"),
            model_version=model_version,
            regime=regime,
        )
        exp = Experience(
            decision_id=decision_id,
            instrument=instrument,
            horizon=horizon,
            regime=regime,
            prediction=expected_return,
            actual=actual_return,
            lesson=lesson,
            failure_type=ftype.value,
            model_version=model_version,
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

        def score(e: Experience) -> int:
            s = 0
            if instrument is not None and e.instrument == instrument:
                s += 4
            if regime is not None and e.regime == regime:
                s += 2
            if horizon is not None and e.horizon == horizon:
                s += 1
            return s

        ranked = sorted(self.experiences, key=score, reverse=True)
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
            walk_forward_passed=walk_forward_passed,
            out_of_sample_passed=out_of_sample_passed,
            stress_passed=stress_passed,
            regression_passed=regression_passed,
            protected_failures_passed=protected_failures_passed,
        )
    )
