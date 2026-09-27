from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from agent.runtime.types import AgentPermission


class AgentMode(StrEnum):
    LEARN = "learn"
    SIMULATE = "simulate"
    PAPER = "paper"
    COPILOT = "copilot"
    SUPERVISED_LIVE = "supervised_live"
    AUTONOMOUS = "autonomous"


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    allowed: bool
    reason: str


class AgentPolicy:
    """
    Central authorization policy.

    Safety rule:
    proposing an order and submitting an order are different permissions.
    """

    MODE_PERMISSIONS: dict[AgentMode, frozenset[AgentPermission]] = {
        AgentMode.LEARN: frozenset({
            AgentPermission.READ_MARKET_DATA,
            AgentPermission.RUN_ANALYSIS,
        }),
        AgentMode.SIMULATE: frozenset({
            AgentPermission.READ_MARKET_DATA,
            AgentPermission.READ_PORTFOLIO,
            AgentPermission.RUN_ANALYSIS,
            AgentPermission.RUN_SIMULATION,
            AgentPermission.PROPOSE_TRADE,
        }),
        AgentMode.PAPER: frozenset({
            AgentPermission.READ_MARKET_DATA,
            AgentPermission.READ_PORTFOLIO,
            AgentPermission.READ_RISK,
            AgentPermission.RUN_ANALYSIS,
            AgentPermission.RUN_SIMULATION,
            AgentPermission.PROPOSE_TRADE,
            AgentPermission.SUBMIT_ORDER,
            AgentPermission.CANCEL_ORDER,
        }),
        AgentMode.COPILOT: frozenset({
            AgentPermission.READ_MARKET_DATA,
            AgentPermission.READ_PORTFOLIO,
            AgentPermission.READ_RISK,
            AgentPermission.RUN_ANALYSIS,
            AgentPermission.RUN_SIMULATION,
            AgentPermission.PROPOSE_TRADE,
            AgentPermission.CANCEL_ORDER,
        }),
        AgentMode.SUPERVISED_LIVE: frozenset({
            AgentPermission.READ_MARKET_DATA,
            AgentPermission.READ_PORTFOLIO,
            AgentPermission.READ_RISK,
            AgentPermission.RUN_ANALYSIS,
            AgentPermission.RUN_SIMULATION,
            AgentPermission.PROPOSE_TRADE,
            AgentPermission.SUBMIT_ORDER,
            AgentPermission.CANCEL_ORDER,
        }),
        AgentMode.AUTONOMOUS: frozenset({
            AgentPermission.READ_MARKET_DATA,
            AgentPermission.READ_PORTFOLIO,
            AgentPermission.READ_RISK,
            AgentPermission.RUN_ANALYSIS,
            AgentPermission.RUN_SIMULATION,
            AgentPermission.PROPOSE_TRADE,
            AgentPermission.SUBMIT_ORDER,
            AgentPermission.CANCEL_ORDER,
        }),
    }

    def __init__(self, mode: AgentMode = AgentMode.LEARN) -> None:
        self._mode = mode

    @property
    def mode(self) -> AgentMode:
        return self._mode

    def set_mode(self, mode: AgentMode) -> None:
        self._mode = mode

    def permissions(self) -> frozenset[AgentPermission]:
        return self.MODE_PERMISSIONS[self._mode]

    def authorize(self, permission: AgentPermission) -> PolicyDecision:
        if permission in self.permissions():
            return PolicyDecision(
                allowed=True,
                reason="Permission granted by current operating mode.",
            )

        return PolicyDecision(
            allowed=False,
            reason=(
                f"Permission {permission.value!r} is not available "
                f"in mode {self._mode.value!r}."
            ),
        )