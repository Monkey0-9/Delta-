from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from .firewall import RiskFirewall as _CanonicalRiskFirewall
from risk.pre_trade.validation import (
    RiskDecision,
    RiskVerdict,
    TradeIntent,
)


# ============================================================================
# Compatibility status facade
# ============================================================================

class _RiskStatusCompatibility:
    """
    Compatibility facade for older DELTA callers.

    Canonical API:
        APPROVE
        BLOCK

    Legacy API:
        APPROVED
        BLOCKED

    The aliases intentionally reference the canonical RiskVerdict members.
    """

    APPROVE = RiskVerdict.APPROVE
    BLOCK = RiskVerdict.BLOCK

    APPROVED = RiskVerdict.APPROVE
    BLOCKED = RiskVerdict.BLOCK


RiskStatus = _RiskStatusCompatibility


# ============================================================================
# Legacy compatibility result
# ============================================================================

@dataclass(frozen=True, slots=True)
class _LegacyRiskDecision:
    decision_id: str
    status: RiskVerdict
    approved_quantity: Decimal
    reason: str
    limits_version: str


# ============================================================================
# Public DELTA Risk Firewall
# ============================================================================

class RiskFirewall(_CanonicalRiskFirewall):
    """
    Public DELTA Risk Firewall.

    Canonical production API:
        firewall.check(...)

    W53-W59 compatibility API:
        firewall.evaluate(...)

    The compatibility API deliberately does not modify the canonical
    risk/firewall implementation.
    """

    def __init__(
        self,
        *args: Any,
        max_quantity: Decimal | float | int | str | None = None,
        max_gross: Decimal | float | int | str | None = None,
        **kwargs: Any,
    ) -> None:

        # ------------------------------------------------------------------
        # Normal canonical construction
        # ------------------------------------------------------------------

        if max_quantity is None and max_gross is None:
            super().__init__(*args, **kwargs)

            self._legacy_max_quantity: Decimal | None = None
            self._legacy_max_gross: Decimal | None = None

            return

        # ------------------------------------------------------------------
        # Legacy W53-W59 construction
        #
        # IMPORTANT:
        # Do not import RiskLimits from risk.limits.
        #
        # The compatibility API only needs these two limits for evaluate().
        # The canonical firewall remains untouched.
        # ------------------------------------------------------------------

        self._legacy_max_quantity = (
            Decimal(str(max_quantity))
            if max_quantity is not None
            else None
        )

        self._legacy_max_gross = (
            Decimal(str(max_gross))
            if max_gross is not None
            else None
        )

        # If the canonical constructor can be initialized without explicit
        # limits, use it. Otherwise, the legacy evaluate() path remains
        # completely self-contained.
        try:
            super().__init__(*args, **kwargs)
        except TypeError:
            # Legacy compatibility mode must not manufacture or modify the
            # canonical risk configuration.
            #
            # We intentionally do not swallow arbitrary runtime exceptions.
            # Only constructor-signature incompatibility is handled.
            if args or kwargs:
                raise

    # ----------------------------------------------------------------------
    # W53-W59 compatibility API
    # ----------------------------------------------------------------------

    def evaluate(
        self,
        *,
        decision_id: str,
        requested_quantity: Decimal | float | int | str,
        current_gross: Decimal | float | int | str,
        limits_version: str,
    ) -> _LegacyRiskDecision:
        """
        Compatibility-only pre-trade evaluation.

        This method is deterministic and fail-closed.

        It does NOT dispatch orders.
        It does NOT bypass the canonical OMS.
        It does NOT replace RiskFirewall.check().
        """

        requested = Decimal(str(requested_quantity))
        gross = Decimal(str(current_gross))

        # ------------------------------------------------------------------
        # Input validation
        # ------------------------------------------------------------------

        if not decision_id:
            return _LegacyRiskDecision(
                decision_id=decision_id,
                status=RiskVerdict.BLOCK,
                approved_quantity=Decimal("0"),
                reason="Decision ID must not be empty.",
                limits_version=limits_version,
            )

        if not limits_version:
            return _LegacyRiskDecision(
                decision_id=decision_id,
                status=RiskVerdict.BLOCK,
                approved_quantity=Decimal("0"),
                reason="Limits version must not be empty.",
                limits_version=limits_version,
            )

        if requested.is_nan() or requested.is_infinite():
            return _LegacyRiskDecision(
                decision_id=decision_id,
                status=RiskVerdict.BLOCK,
                approved_quantity=Decimal("0"),
                reason="Requested quantity must be finite.",
                limits_version=limits_version,
            )

        if gross.is_nan() or gross.is_infinite():
            return _LegacyRiskDecision(
                decision_id=decision_id,
                status=RiskVerdict.BLOCK,
                approved_quantity=Decimal("0"),
                reason="Current gross exposure must be finite.",
                limits_version=limits_version,
            )

        if requested < Decimal("0"):
            return _LegacyRiskDecision(
                decision_id=decision_id,
                status=RiskVerdict.BLOCK,
                approved_quantity=Decimal("0"),
                reason="Requested quantity cannot be negative.",
                limits_version=limits_version,
            )

        if gross < Decimal("0"):
            return _LegacyRiskDecision(
                decision_id=decision_id,
                status=RiskVerdict.BLOCK,
                approved_quantity=Decimal("0"),
                reason="Current gross exposure cannot be negative.",
                limits_version=limits_version,
            )

        # ------------------------------------------------------------------
        # Quantity limit
        # ------------------------------------------------------------------

        if (
            self._legacy_max_quantity is not None
            and requested > self._legacy_max_quantity
        ):
            return _LegacyRiskDecision(
                decision_id=decision_id,
                status=RiskVerdict.BLOCK,
                approved_quantity=Decimal("0"),
                reason=(
                    f"Requested quantity {requested} exceeds "
                    f"maximum quantity {self._legacy_max_quantity}."
                ),
                limits_version=limits_version,
            )

        # ------------------------------------------------------------------
        # Gross exposure limit
        # ------------------------------------------------------------------

        projected_gross = gross + requested

        if (
            self._legacy_max_gross is not None
            and projected_gross > self._legacy_max_gross
        ):
            return _LegacyRiskDecision(
                decision_id=decision_id,
                status=RiskVerdict.BLOCK,
                approved_quantity=Decimal("0"),
                reason=(
                    f"Projected gross exposure {projected_gross} exceeds "
                    f"maximum gross exposure {self._legacy_max_gross}."
                ),
                limits_version=limits_version,
            )

        # ------------------------------------------------------------------
        # Approved
        # ------------------------------------------------------------------

        return _LegacyRiskDecision(
            decision_id=decision_id,
            status=RiskVerdict.APPROVE,
            approved_quantity=requested,
            reason="Risk checks passed.",
            limits_version=limits_version,
        )


__all__ = [
    "RiskFirewall",
    "RiskDecision",
    "RiskVerdict",
    "RiskStatus",
    "TradeIntent",
]