"""Phase 8 — Financial permission hierarchy (allow/ask/deny per capability).

Invariant: the MODEL can never grant itself permission, alter risk limits,
unlock live trading, or disable the kill switch. It may REQUEST an action;
policy decides.
"""
from __future__ import annotations


HIERARCHY = ("READ", "MARKET_RESEARCH", "PORTFOLIO_READ", "RISK_READ",
             "PAPER_TRADE", "ORDER_STAGE", "ORDER_CANCEL", "LIVE_EXECUTION",
             "BROKER_ADMIN", "RISK_ADMIN", "SYSTEM_ADMIN", "KILL_SWITCH", "UNLOCK")

TOOL_POLICY: dict[str, str] = {
    "market.quote": "ALLOW",
    "portfolio.read": "ALLOW",
    "order.stage": "ALLOW",
    "paper.submit": "ALLOW",
    "live.submit": "ASK",
    "live.cancel": "ASK",
    "risk.override": "DENY",
    "kill.switch": "ALLOW",
    "live.unlock": "ASK+AUTH",
}


class PermissionDenied(Exception):
    pass


def check(tool: str, grants: set[str] | None = None) -> str:
    """Returns ALLOW/ASK/DENY. Model self-grant attempts always DENY."""
    rule = TOOL_POLICY.get(tool, "ASK")
    if rule == "DENY":
        raise PermissionDenied(f"{tool}: DENY (model cannot override)")
    return rule


def model_may_not(action: str) -> bool:
    return action in ("grant permission", "alter risk limits",
                      "unlock live trading", "disable kill switch")


__all__ = ["HIERARCHY", "TOOL_POLICY", "PermissionDenied", "check", "model_may_not"]
