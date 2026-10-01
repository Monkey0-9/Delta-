from __future__ import annotations

from uuid import uuid4

from agent.planner.planner import AgentPlanner, PlanStepKind
from agent.policies.policy import AgentMode, AgentPolicy
from agent.runtime.runtime import AgentRuntime
from agent.runtime.types import (
    AgentPermission,
    AgentTask,
    ToolCall,
)
from agent.tools.registry import ToolRegistry


def test_agent_task_requires_instruction() -> None:
    try:
        AgentTask(instruction="")
    except ValueError:
        return

    raise AssertionError("Empty instruction must fail.")


def test_planner_creates_portfolio_analysis_plan() -> None:
    task = AgentTask(
        instruction="Analyze my portfolio and find opportunities."
    )

    plan = AgentPlanner().create_plan(task)

    assert plan.task_id == task.task_id
    assert len(plan.steps) >= 2
    assert plan.steps[0].kind == PlanStepKind.OBSERVE


def test_learn_mode_denies_order_submission() -> None:
    policy = AgentPolicy(AgentMode.LEARN)

    decision = policy.authorize(
        AgentPermission.SUBMIT_ORDER
    )

    assert decision.allowed is False


def test_paper_mode_allows_submission() -> None:
    policy = AgentPolicy(AgentMode.PAPER)

    decision = policy.authorize(
        AgentPermission.SUBMIT_ORDER
    )

    assert decision.allowed is True


def test_tool_registry_enforces_permissions() -> None:
    registry = ToolRegistry()

    registry.register(
        name="private_trade_tool",
        description="Test trading tool",
        function=lambda: "executed",
        permissions=frozenset({
            AgentPermission.SUBMIT_ORDER,
        }),
    )

    call = ToolCall(
        name="private_trade_tool",
        arguments={},
        task_id=uuid4(),
    )

    result = registry.execute(
        call,
        frozenset({
            AgentPermission.READ_MARKET_DATA,
        }),
    )

    assert result.success is False
    assert result.error is not None


def test_tool_registry_allows_authorized_call() -> None:
    registry = ToolRegistry()

    registry.register(
        name="analysis",
        description="Analysis tool",
        function=lambda symbol: f"analysis:{symbol}",
        permissions=frozenset({
            AgentPermission.RUN_ANALYSIS,
        }),
    )

    task_id = uuid4()

    result = registry.execute(
        ToolCall(
            name="analysis",
            arguments={"symbol": "NVDA"},
            task_id=task_id,
        ),
        frozenset({
            AgentPermission.RUN_ANALYSIS,
        }),
    )

    assert result.success is True
    assert result.output == "analysis:NVDA"


def test_agent_runtime_validates_plan() -> None:
    runtime = AgentRuntime(
        planner=AgentPlanner(),
        policy=AgentPolicy(AgentMode.LEARN),
    )

    task = AgentTask(
        instruction="Analyze my portfolio."
    )

    result = runtime.execute(task)

    assert result.task_id == task.task_id
    assert result.status.value == "failed"
    assert result.messages


def test_agent_runtime_allows_analysis_in_learn_mode() -> None:
    # Real path: runtime executes tools through the typed executor.
    # COMPLETED requires actual execution, recorded in the ledger.
    from ai.contracts import RiskClass, ToolDefinition
    from ai.executor import TypedToolExecutor

    ran: list[str] = []
    executor = TypedToolExecutor()
    executor.register(
        ToolDefinition(name="run_analysis", permission="run_analysis",
                       risk_class=RiskClass.READ_ONLY,
                       input_schema={"type": "object"}),
        lambda query="": ran.append(query) or {"analysis": query},
    )
    runtime = AgentRuntime(
        planner=AgentPlanner(),
        policy=AgentPolicy(AgentMode.LEARN),
        executor=executor,
        agent_id="test-agent",
        grants=("run_analysis",),
    )

    task = AgentTask(
        instruction="Analyze NVDA."
    )

    result = runtime.execute(task)

    assert result.status.value == "completed"
    assert ran, "tool must actually execute"
    assert any(e["kind"] == "tool" and e["status"] == "ok"
               for e in executor.ledger.entries)


def test_agent_runtime_without_executor_refuses_fake_completion() -> None:
    runtime = AgentRuntime(
        planner=AgentPlanner(),
        policy=AgentPolicy(AgentMode.LEARN),
    )

    task = AgentTask(
        instruction="Analyze NVDA."
    )

    result = runtime.execute(task)

    # Tool steps with no executor: FAILED, never fake COMPLETED.
    assert result.status.value == "failed"
    assert any("no executor" in m for m in result.messages)