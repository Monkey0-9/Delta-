"""Agent budgets + compensating-action rollback (Stream D P0).

Every agent gets max_steps/tokens/calls/runtime/cost/retries.
Trading has no DB-undo: failed plans use compensating actions.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal


@dataclass(frozen=True, slots=True)
class AgentBudget:
    max_steps: int = 20
    max_tool_calls: int = 50
    timeout_s: float = 120.0
    max_tokens: int = 16000
    max_cost_usd: float = 1.0
    max_retries: int = 2

    def __post_init__(self) -> None:
        assert self.max_steps > 0 and self.max_tool_calls > 0
        assert self.timeout_s > 0 and self.max_tokens > 0


DEFAULT_BUDGETS: dict[str, AgentBudget] = {
    "research": AgentBudget(20, 50, 120.0, 16000, 1.0, 2),
    "alpha": AgentBudget(15, 40, 90.0, 12000, 0.75, 2),
    "portfolio": AgentBudget(10, 20, 60.0, 8000, 0.5, 1),
    "risk": AgentBudget(8, 15, 30.0, 6000, 0.25, 1),
    "execution": AgentBudget(10, 20, 60.0, 8000, 0.5, 1),
    "news": AgentBudget(12, 30, 60.0, 8000, 0.4, 2),
    "critic": AgentBudget(6, 10, 45.0, 6000, 0.25, 1),
}


@dataclass(slots=True)
class BudgetTracker:
    budget: AgentBudget
    steps: int = 0
    tool_calls: int = 0
    tokens: int = 0
    cost_usd: float = 0.0
    retries: int = 0
    started_at: datetime | None = None

    def start(self) -> None:
        self.started_at = datetime.now(timezone.utc)

    def check(self) -> tuple[bool, str]:
        if self.steps >= self.budget.max_steps:
            return False, f"budget: max_steps {self.budget.max_steps} reached"
        if self.tool_calls >= self.budget.max_tool_calls:
            return False, "budget: max_tool_calls reached"
        if self.tokens >= self.budget.max_tokens:
            return False, "budget: max_tokens reached"
        if self.cost_usd >= self.budget.max_cost_usd:
            return False, "budget: max_cost reached"
        if self.started_at and (datetime.now(timezone.utc) - self.started_at).total_seconds() > self.budget.timeout_s:
            return False, "budget: timeout"
        return True, "ok"


CompensationKind = Literal["cancel_order", "flatten_position", "revoke_plan", "noop"]


@dataclass(frozen=True, slots=True)
class CompensatingAction:
    kind: CompensationKind
    ref: str
    reason: str


def rollback_plan(action_ids: tuple[str, ...], reason: str) -> tuple[CompensatingAction, ...]:
    """Live fills cannot be DB-undone — emit compensating actions instead."""
    return tuple(CompensatingAction(kind="revoke_plan", ref=a, reason=reason) for a in action_ids)


__all__ = ["AgentBudget", "DEFAULT_BUDGETS", "BudgetTracker", "CompensatingAction", "rollback_plan"]
