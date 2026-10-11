from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
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
    # M-item (P3): replayable tool trace — one record per executed step.
    # Default keeps every existing constructor working.
    trace: tuple[dict[str, Any], ...] = ()


@dataclass(frozen=True, slots=True)
class ToolApproval:
    task_id: UUID
    tool_name: str
    approver: str
    at: str = ""


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

    # M-item (P3): tool calls that mutate the world (or enable autonomy)
    # require a recorded human approval per task+tool — in EVERY mode,
    # including AUTONOMOUS and PAPER. Modes differ in what they may hold;
    # nothing executes sensitive tools on mode membership alone.
    SENSITIVE_PERMISSIONS = frozenset({
        "submit_order", "cancel_order", "enable_autonomous"})

    def __init__(
        self,
        planner: AgentPlanner,
        policy: AgentPolicy,
        executor: Any | None = None,
        agent_id: str = "agent",
        grants: tuple[str, ...] = (),
        budget_key: str = "research",
    ) -> None:
        self._planner = planner
        self._policy = policy
        self._executor = executor
        self._agent_id = agent_id
        self._budget_key = budget_key
        self._approvals: list[ToolApproval] = []
        if executor is not None:
            for tool in grants:
                try:
                    executor.grant(agent_id, tool)
                except Exception:
                    pass

    def approve(self, task_id: UUID, tool_name: str, approver: str) -> ToolApproval:
        """Record a human approval for one task+tool. Approvals are
        per-task (never standing): a new task needs a new grant."""
        if not approver.strip():
            raise ValueError("approver identity required.")
        approval = ToolApproval(
            task_id=task_id, tool_name=tool_name, approver=approver.strip(),
            at=datetime.now(timezone.utc).isoformat())
        self._approvals.append(approval)
        return approval

    def _is_approved(self, task_id: UUID, tool_name: str) -> bool:
        return any(a.task_id == task_id and a.tool_name == tool_name
                   for a in self._approvals)

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
            elif (step.required_permission in self.SENSITIVE_PERMISSIONS
                    and step.tool_name
                    and not self._is_approved(plan.task_id, step.tool_name)):
                messages.append(
                    f"DENIED: step {step.sequence} ({step.tool_name}): "
                    f"sensitive permission {step.required_permission!r} "
                    f"requires a recorded human approval — none on file."
                )

        return tuple(messages)

    def execute(self, task: AgentTask) -> AgentRunResult:
        from agent.runtime.budgets import DEFAULT_BUDGETS, BudgetTracker
        budget = DEFAULT_BUDGETS.get(self._budget_key,
                                     DEFAULT_BUDGETS["research"])
        tracker = BudgetTracker(budget=budget)
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
        trace: list[dict[str, Any]] = []
        executor = self._executor
        assert executor is not None  # guarded above: tool_steps require executor
        for step in tool_steps:
            good, bmsg = tracker.check()
            if not good:
                messages.append(f"ABORTED step {step.sequence}: {bmsg}")
                return AgentRunResult(task_id=task.task_id,
                                      status=AgentTaskStatus.ABORTED,
                                      plan=plan, messages=tuple(messages),
                                      trace=tuple(trace))
            # M-item (P3): every attempted step counts. Steps/retries are
            # enforced here; tokens/cost accrue from executor-reported usage
            # when present (getattr defaults keep non-reporting executors
            # honest rather than crashing).
            tracker.steps += 1
            step_ts = datetime.now(timezone.utc).isoformat()
            try:
                result = executor.execute_step(
                    self._agent_id, step.tool_name,
                    dict(step.tool_arguments or {}), task.task_id)
            except Exception as exc:
                tracker.retries += 1
                messages.append(f"FAILED step {step.sequence} "
                                f"{step.tool_name}: {exc}")
                trace.append({"seq": step.sequence, "tool": step.tool_name,
                              "status": "exception",
                              "error": f"{type(exc).__name__}: {exc}",
                              "ts": step_ts})
                failed += 1
                continue
            ran += 1
            tracker.tool_calls += 1
            tokens_used = int(getattr(result, "tokens_used", 0) or 0)
            tracker.tokens += tokens_used
            try:
                cost_used = float(getattr(result, "cost_usd", 0.0) or 0.0)
            except (TypeError, ValueError):
                cost_used = 0.0
            tracker.cost_usd += cost_used
            status = str(getattr(result, "status", "error"))
            trace.append({"seq": step.sequence, "tool": step.tool_name,
                          "status": status,
                          "error": getattr(result, "error", ""),
                          "tokens": tokens_used, "cost_usd": cost_used,
                          "ts": step_ts})
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
                                  plan=plan, messages=tuple(messages),
                                  trace=tuple(trace))
        messages.append(f"Executed {ran}/{len(tool_steps)} tool steps "
                        f"via typed executor.")
        return AgentRunResult(
            task_id=task.task_id,
            status=AgentTaskStatus.COMPLETED,
            plan=plan,
            messages=tuple(messages),
            trace=tuple(trace),
        )