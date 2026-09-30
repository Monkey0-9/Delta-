"""DEPRECATED — quarantined shadow firewall (float, partial-approve semantics).

Do NOT import in new code. The sanctioned pre-trade path is
``risk.firewall.firewall.RiskFirewall`` (Decimal, fail-closed BLOCK) via
``core.oms.gateway.OrderGateway``. This module is retained only so legacy
callers fail loudly at import review, not silently at runtime.
"""
from __future__ import annotations

import warnings

warnings.warn(
    "risk.firewall_legacy_float is deprecated; use risk.firewall.firewall.RiskFirewall",
    DeprecationWarning,
    stacklevel=2,
)

from dataclasses import dataclass
from enum import Enum

try:
    from delta_omega.agent_ledger_gate import RiskHaltException as RiskHaltException
except ImportError:  # pragma: no cover
    class RiskHaltException(RuntimeError):  # type: ignore[no-redef]
        """Uncatchable-by-policy halt (fallback if kernel unimportable)."""


def enforce_red_button(gate_state) -> None:
    """Step 1.4 bridge: raise RiskHaltException when the kernel gate trips."""
    from delta_omega.agent_ledger_gate import red_button

    trips = red_button(gate_state)
    if trips:
        raise RiskHaltException(f"RED-BUTTON HALT: {trips}")


class RiskStatus(str, Enum):
    APPROVED = "APPROVED"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True, slots=True)
class RiskDecision:

    decision_id: str
    status: RiskStatus
    approved_quantity: float
    reason: str
    limits_version: str


class RiskFirewall:

    def __init__(
        self,
        max_quantity: float,
        max_gross: float,
    ):
        if max_quantity <= 0:
            raise ValueError(
                "max_quantity must be positive"
            )

        if max_gross <= 0:
            raise ValueError(
                "max_gross must be positive"
            )

        self.max_quantity = max_quantity
        self.max_gross = max_gross

    def evaluate_with_red_button(
        self,
        *,
        decision_id: str,
        requested_quantity: float,
        current_gross: float,
        limits_version: str,
        gate_state=None,
    ) -> RiskDecision:
        """Step 1.4 bridge: kernel red_button runs before any approval.

        Raises RiskHaltException (uncatchable-by-policy) on any trip.
        """
        if gate_state is not None:
            enforce_red_button(gate_state)
        return self.evaluate(
            decision_id=decision_id,
            requested_quantity=requested_quantity,
            current_gross=current_gross,
            limits_version=limits_version,
        )

    def evaluate(
        self,
        *,
        decision_id: str,
        requested_quantity: float,
        current_gross: float,
        limits_version: str,
    ) -> RiskDecision:

        if requested_quantity <= 0:
            return RiskDecision(
                decision_id,
                RiskStatus.BLOCKED,
                0.0,
                "invalid quantity",
                limits_version,
            )

        if current_gross >= self.max_gross:
            return RiskDecision(
                decision_id,
                RiskStatus.BLOCKED,
                0.0,
                "gross exposure limit",
                limits_version,
            )

        available = (
            self.max_gross
            - current_gross
        )

        approved = min(
            requested_quantity,
            self.max_quantity,
            available,
        )

        if approved <= 0:
            return RiskDecision(
                decision_id,
                RiskStatus.BLOCKED,
                0.0,
                "no risk capacity",
                limits_version,
            )

        return RiskDecision(
            decision_id,
            RiskStatus.APPROVED,
            approved,
            "risk checks passed",
            limits_version,
        )