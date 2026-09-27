from __future__ import annotations

from decimal import Decimal

from memory.failures.failure import FailureType


class FailureAttributor:
    """
    Deterministic first-pass attribution.

    This is deliberately conservative.
    Ambiguous failures become UNKNOWN rather than being
    incorrectly attributed.
    """

    def classify(
        self,
        *,
        expected_return: Decimal,
        actual_return: Decimal,
        data_valid: bool,
        execution_slippage: Decimal,
        predicted_regime: str,
        realized_regime: str,
        risk_breached: bool,
    ) -> FailureType:

        if not data_valid:
            return FailureType.DATA_ERROR

        if risk_breached:
            return FailureType.RISK_ERROR

        if abs(execution_slippage) > Decimal("0.01"):
            return FailureType.EXECUTION_ERROR

        if predicted_regime != realized_regime:
            return FailureType.REGIME_ERROR

        error = abs(expected_return - actual_return)

        if error <= Decimal("0.01"):
            return FailureType.NO_FAILURE

        if abs(expected_return) > Decimal("0.02"):
            return FailureType.MODEL_ERROR

        return FailureType.DECISION_ERROR