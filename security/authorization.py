from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Permission(StrEnum):
    READ_MARKET = "read_market"
    READ_PORTFOLIO = "read_portfolio"
    READ_RISK = "read_risk"

    ANALYZE = "analyze"
    SIMULATE = "simulate"

    PROPOSE_TRADE = "propose_trade"
    SUBMIT_ORDER = "submit_order"
    CANCEL_ORDER = "cancel_order"

    ENABLE_AUTONOMOUS = "enable_autonomous"


@dataclass(frozen=True, slots=True)
class AuthorizationDecision:
    allowed: bool
    reason: str


class AuthorizationEngine:
    """
    Central authorization boundary.

    No agent/tool/broker component should bypass this layer.
    """

    def __init__(
        self,
        permissions: frozenset[Permission],
    ) -> None:
        self._permissions = permissions

    def authorize(
        self,
        permission: Permission,
    ) -> AuthorizationDecision:
        if permission in self._permissions:
            return AuthorizationDecision(
                allowed=True,
                reason="permission granted",
            )

        return AuthorizationDecision(
            allowed=False,
            reason=f"permission denied: {permission.value}",
        )

    def require(self, permission: Permission) -> None:
        decision = self.authorize(permission)

        if not decision.allowed:
            raise PermissionError(decision.reason)