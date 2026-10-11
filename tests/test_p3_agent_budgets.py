"""P3: agent budgets are enforced for real (steps/retries/tokens/cost)."""
from __future__ import annotations

import sys
from uuid import uuid4

sys.path.insert(0, ".")

from agent.planner.planner import AgentPlan, AgentPlanner, PlanStep, PlanStepKind
from agent.policies.policy import AgentPolicy
from agent.runtime.runtime import AgentRuntime
from agent.runtime.types import AgentTask, AgentTaskStatus


class _StubPlanner(AgentPlanner):
    def __init__(self, n_steps: int):
        super().__init__()
        self._n = n_steps

    def create_plan(self, task: AgentTask) -> AgentPlan:
        return AgentPlan(
            task_id=task.task_id,
            steps=tuple(
                PlanStep(sequence=i, kind=PlanStepKind.ANALYZE,
                         description=f"step {i}", tool_name="echo",
                         tool_arguments={})
                for i in range(1, self._n + 1)))


class _StubExecutor:
    def __init__(self, fail_on: tuple[int, ...] = ()):
        self.calls: list[str] = []
        self._fail_on = set(fail_on)
        self._n = 0

    def grant(self, agent_id: str, tool: str) -> None:
        return None

    def execute_step(self, agent_id: str, tool_name: str, arguments: dict,
                     task_id):
        self._n += 1
        self.calls.append(tool_name)
        if self._n in self._fail_on:
            raise RuntimeError("boom")

        class _R:
            status = "ok"
            error = ""
            tokens_used = 100
            cost_usd = 0.01

        return _R()


def _rt(n_steps: int, **kw):
    calls = {"n": n_steps}

    class _P(_StubPlanner):
        def __init__(self):
            super().__init__(calls["n"])

    rt = AgentRuntime(_P(), AgentPolicy(), executor=_StubExecutor(), **kw)
    return rt


def test_step_budget_aborts_long_plans():
    rt = _rt(30)  # research budget: 20 steps
    res = rt.execute(AgentTask(instruction="run analysis"))
    assert res.status == AgentTaskStatus.ABORTED, res.messages
    assert any("max_steps" in m for m in res.messages)


def test_reported_usage_accounted_without_false_abort():
    # 100 tokens/call against the critic budget (6000) with a short plan
    # must still finish; shrink steps so tokens are the binding constraint.
    rt = _rt(3, budget_key="critic")
    res = rt.execute(AgentTask(instruction="run analysis"))
    assert res.status == AgentTaskStatus.COMPLETED, res.messages


def test_executor_exceptions_count_as_retries_and_do_not_complete():
    rt = AgentRuntime(_StubPlanner(2), AgentPolicy(),
                      executor=_StubExecutor(fail_on=(1, 2)))
    res = rt.execute(AgentTask(instruction="run analysis"))
    assert res.status in (AgentTaskStatus.FAILED, AgentTaskStatus.PARTIAL), \
        res.messages


def test_per_role_budget_key_respected():
    # Unknown key falls back to research; known key uses its own limits.
    rt = AgentRuntime(_StubPlanner(1), AgentPolicy(),
                      executor=_StubExecutor(), budget_key="risk")
    res = rt.execute(AgentTask(instruction="run analysis"))
    assert res.status == AgentTaskStatus.COMPLETED, res.messages


def _sensitive_plan(task_id):
    from agent.planner.planner import AgentPlan, PlanStep, PlanStepKind

    return AgentPlan(
        task_id=task_id,
        steps=(PlanStep(sequence=1, kind=PlanStepKind.PROPOSE,
                        description="submit order", tool_name="place_order",
                        tool_arguments={"symbol": "AAPL"},
                        required_permission="submit_order"),))


def test_sensitive_tool_requires_recorded_approval():
    from agent.policies.policy import AgentMode, AgentPolicy

    task = AgentTask(instruction="buy AAPL")
    policy = AgentPolicy(mode=AgentMode.PAPER)  # grants submit_order...
    rt = AgentRuntime(_StubPlanner(1), policy, executor=_StubExecutor())
    plan = _sensitive_plan(task.task_id)
    violations = rt.validate_plan(plan)
    assert any("approval" in v for v in violations), violations
    # ...but mode membership alone never suffices, not even AUTONOMOUS.
    auto = AgentRuntime(_StubPlanner(1), AgentPolicy(mode=AgentMode.AUTONOMOUS),
                        executor=_StubExecutor())
    assert any("approval" in v for v in auto.validate_plan(plan))
    # A recorded human grant clears exactly that task+tool.
    rt.approve(task.task_id, "place_order", approver=" op-risk ")
    assert rt.validate_plan(plan) == ()
    other = AgentTask(instruction="buy MSFT")
    assert any("approval" in v
               for v in rt.validate_plan(_sensitive_plan(other.task_id)))


def test_trace_records_every_step():
    rt = AgentRuntime(_StubPlanner(3), AgentPolicy(),
                      executor=_StubExecutor())
    res = rt.execute(AgentTask(instruction="run analysis"))
    assert res.status == AgentTaskStatus.COMPLETED, res.messages
    assert [t["seq"] for t in res.trace] == [1, 2, 3]
    assert all(t["status"] == "ok" and t["tool"] == "echo" for t in res.trace)
    assert all(t["tokens"] == 100 and t["ts"] for t in res.trace)
