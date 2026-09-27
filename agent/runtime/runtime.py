from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from agent.planner.planner import AgentPlan, AgentPlanner
from agent.policies.policy import AgentPolicy
from agent.runtime.types import AgentTask, AgentTaskStatus


@dataclass(frozen=True, slots=True)
class AgentRunResult:
    task_id: UUID
    status: AgentTaskStatus
    plan: AgentPlan
    messages: tuple[str, ...]


class AgentRuntime:
    """
    Deterministic orchestration layer.

    Important:
    This layer creates plans and controls tools.
    It does not contain broker execution logic.
    """

    def __init__(
        self,
        planner: AgentPlanner,
        policy: AgentPolicy,
    ) -> None:
        self._planner = planner
        self._policy = policy

    def plan(self, task: AgentTask) -> AgentPlan:
        return self._planner.create_plan(task)

    def validate_plan(self, plan: AgentPlan) -> tuple[str, ...]:
        messages: list[str] = []

        for step in plan.steps:
            if step.required_permission is None:
                continue

            permission = next(
                (
                    p
                    for p in self._policy.permissions()
                    if p.value == step.required_permission
                ),
                None,
            )

            if permission is None:
                messages.append(
                    f"DENIED: step {step.sequence}: {step.description}"
                )

        return tuple(messages)

    def execute(self, task: AgentTask) -> AgentRunResult:
        plan = self.plan(task)
        violations = self.validate_plan(plan)

        if violations:
            return AgentRunResult(
                task_id=task.task_id,
                status=AgentTaskStatus.FAILED,
                plan=plan,
                messages=violations,
            )

        return AgentRunResult(
            task_id=task.task_id,
            status=AgentTaskStatus.COMPLETED,
            plan=plan,
            messages=("Plan validated successfully.",),
        )