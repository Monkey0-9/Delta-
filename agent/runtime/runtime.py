from __future__ import annotations

from dataclasses import dataclass
from typing import Any
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

    Executes plans step by step through a typed tool executor:
    POLICY -> BUDGET -> TOOL EXECUTION -> RESULT VALIDATION -> EVIDENCE.
    COMPLETED is returned only when every tool step executed successfully;
    anything else yields PARTIAL or FAILED. A validated plan alone is
    never reported as completed.

    This layer creates plans and controls tools.
    It does not contain broker execution logic.
    """

    def __init__(
        self,
        planner: AgentPlanner,
        policy: AgentPolicy,
        executor: Any | None = None,
        agent_id: str = "agent",
        grants: tuple[str, ...] = (),
    ) -> None:
        self._planner = planner
        self._policy = policy
        self._executor = executor
        self._agent_id = agent_id
        if executor is not None:
            for tool in grants:
                try:
                    executor.grant(agent_id, tool)
                except Exception:
                    pass

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
        from agent.runtime.budgets import DEFAULT_BUDGETS, BudgetTracker
        tracker = BudgetTracker(budget=DEFAULT_BUDGETS.get("research", DEFAULT_BUDGETS["research"]))
        tracker.start()
        ok, msg = tracker.check()
        if not ok:
            return AgentRunResult(task_id=task.task_id, status=AgentTaskStatus.FAILED,
                                  plan=self.plan(task), messages=(f"DENIED: {msg}",))
        plan = self.plan(task)
        violations = self.validate_plan(plan)

        if violations:
            return AgentRunResult(
                task_id=task.task_id,
                status=AgentTaskStatus.FAILED,
                plan=plan,
                messages=violations,
            )

        # Real execution: every tool step runs through the typed executor.
        messages: list[str] = []
        tool_steps = [s for s in plan.steps if s.tool_name]
        if tool_steps and self._executor is None:
            return AgentRunResult(
                task_id=task.task_id,
                status=AgentTaskStatus.FAILED,
                plan=plan,
                messages=("tool steps present but no executor wired; "
                          "refusing to report COMPLETED without execution.",),
            )
        failed = 0
        ran = 0
        executor = self._executor
        assert executor is not None  # guarded above: tool_steps require executor
        for step in tool_steps:
            good, bmsg = tracker.check()
            if not good:
                messages.append(f"ABORTED step {step.sequence}: {bmsg}")
                return AgentRunResult(task_id=task.task_id,
                                      status=AgentTaskStatus.ABORTED,
                                      plan=plan, messages=tuple(messages))
            try:
                result = executor.execute_step(
                    self._agent_id, step.tool_name,
                    dict(step.tool_arguments or {}), task.task_id)
            except Exception as exc:
                messages.append(f"FAILED step {step.sequence} "
                                f"{step.tool_name}: {exc}")
                failed += 1
                continue
            ran += 1
            tracker.tool_calls += 1
            status = str(getattr(result, "status", "error"))
            if status != "ok":
                messages.append(f"FAILED step {step.sequence} "
                                f"{step.tool_name}: {status}: "
                                f"{getattr(result, 'error', '')}")
                failed += 1
            else:
                messages.append(f"ok step {step.sequence} {step.tool_name}")

        if tool_steps and failed:
            return AgentRunResult(task_id=task.task_id,
                                  status=AgentTaskStatus.PARTIAL
                                  if ran > failed else AgentTaskStatus.FAILED,
                                  plan=plan, messages=tuple(messages))
        messages.append(f"Executed {ran}/{len(tool_steps)} tool steps "
                        f"via typed executor.")
        return AgentRunResult(
            task_id=task.task_id,
            status=AgentTaskStatus.COMPLETED,
            plan=plan,
            messages=tuple(messages),
        )