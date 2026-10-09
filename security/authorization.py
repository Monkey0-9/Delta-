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

    KILL_SWITCH = "kill_switch"
    UNLOCK = "unlock"


class Role(StrEnum):
    """Operator roles, lowest privilege first.

    Rank order (defines ``RISK_OFFICER+``): RESEARCHER < QUANT <
    RISK_OFFICER < OPERATOR < ADMIN. Kill / unlock / order-route require
    RISK_OFFICER or above.

    NOTE (next step, out of scope): MFA and per-operator credential expiry
    are not enforced here — role strings are caller-asserted. A future
    change should bind roles to authenticated operator identities with
    expiring tokens.
    """

    RESEARCHER = "researcher"
    QUANT = "quant"
    RISK_OFFICER = "risk_officer"
    OPERATOR = "operator"
    ADMIN = "admin"


_ROLE_RANK: dict[Role, int] = {
    Role.RESEARCHER: 0,
    Role.QUANT: 1,
    Role.RISK_OFFICER: 2,
    Role.OPERATOR: 3,
    Role.ADMIN: 4,
}

# Minimum role required per permission. Read/analyze/simulate are open to
# all roles; anything that moves money or the kill switch needs RISK_OFFICER+.
_MIN_ROLE_FOR_PERMISSION: dict[Permission, Role] = {
    Permission.READ_MARKET: Role.RESEARCHER,
    Permission.READ_PORTFOLIO: Role.RESEARCHER,
    Permission.READ_RISK: Role.RESEARCHER,
    Permission.ANALYZE: Role.RESEARCHER,
    Permission.SIMULATE: Role.RESEARCHER,
    Permission.PROPOSE_TRADE: Role.QUANT,
    Permission.SUBMIT_ORDER: Role.RISK_OFFICER,
    Permission.CANCEL_ORDER: Role.RISK_OFFICER,
    Permission.ENABLE_AUTONOMOUS: Role.RISK_OFFICER,
    Permission.KILL_SWITCH: Role.RISK_OFFICER,
    Permission.UNLOCK: Role.RISK_OFFICER,
}


def role_rank(role: Role | str) -> int:
    """Numeric privilege rank (higher = more privilege); unknown -> -1."""
    resolved = normalize_role(role)
    if resolved is None:
        return -1
    return _ROLE_RANK[resolved]


def normalize_role(role: Role | str) -> Role | None:
    """Map a caller-supplied role string to a Role; None when unknown."""
    if isinstance(role, Role):
        return role
    if not isinstance(role, str):
        return None
    try:
        return Role(role.strip().lower().replace("-", "_"))
    except ValueError:
        return None


def role_can(role: Role | str, permission: Permission) -> bool:
    """True when the role meets the minimum rank for the permission.

    Unknown roles (unparseable strings) are always refused.
    """
    resolved = normalize_role(role)
    if resolved is None:
        return False
    required = _MIN_ROLE_FOR_PERMISSION.get(permission, Role.ADMIN)
    return _ROLE_RANK[resolved] >= _ROLE_RANK[required]


def permissions_for_role(role: Role | str) -> frozenset[Permission]:
    """All permissions granted to a role. Unknown roles get nothing."""
    resolved = normalize_role(role)
    if resolved is None:
        return frozenset()
    return frozenset(p for p in Permission if role_can(resolved, p))


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

    @classmethod
    def for_role(cls, role: Role | str) -> AuthorizationEngine:
        """Build an engine holding exactly the permissions of a role."""
        return cls(permissions_for_role(role))