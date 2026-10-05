"""Group 04 — Permission layer: kill/risk bypass LLM, write ops need confirm.

Frozen rule (vNext): Ctrl+X K then /kill CONFIRM bypasses LLM, hits risk governor.
Ctrl+K alone is never kill. Risky commands require explicit confirmation.
"""
from __future__ import annotations

from dataclasses import dataclass


BYPASS_LLM = frozenset({"kill", "kill-switch", "risk"})
WRITE_OPS = frozenset({"kill", "kill-switch", "trade", "execution", "config"})


@dataclass(frozen=True)
class PermissionDecision:
    allowed: bool
    bypass_llm: bool
    needs_confirm: bool
    reason: str


def check(command: str, *, confirmed: bool = False, mode: str = "PAPER") -> PermissionDecision:
    name = (command or "").lower().strip("/ ")
    if name in ("kill", "kill-switch"):
        if not confirmed:
            return PermissionDecision(False, True, True, "kill requires CONFIRM token")
        return PermissionDecision(True, True, False, "kill bypasses LLM, hits governor")
    if name in BYPASS_LLM:
        return PermissionDecision(True, True, False, "risk bypasses LLM")
    if name in WRITE_OPS:
        if not confirmed:
            return PermissionDecision(False, False, True, "write op needs confirm")
        return PermissionDecision(True, False, False, "confirmed write op")
    return PermissionDecision(True, False, False, "read-only")
