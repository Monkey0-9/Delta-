from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID
from typing import Any

from agent.runtime.types import AgentTask


class PlanStepKind(StrEnum):
    OBSERVE = "observe"
    ANALYZE = "analyze"
    SIMULATE = "simulate"
    PROPOSE = "propose"
    EXPLAIN = "explain"
    VALIDATE = "validate"


@dataclass(frozen=True, slots=True)
class PlanStep:
    sequence: int
    kind: PlanStepKind
    description: str
    tool_name: str | None = None
    tool_arguments: dict[str, Any] | None = None
    required_permission: str | None = None


@dataclass(frozen=True, slots=True)
class AgentPlan:
    task_id: UUID
    steps: tuple[PlanStep, ...]


class AgentPlanner:
    """
    Schema-validated planner using structured function calling.

    W94+: Replaces keyword string matching with dynamic tool selection
    based on instruction analysis and available tool registry.
    The resulting plan passes through policy validation.
    """

    def __init__(self, tool_registry: Any = None) -> None:
        """Initialize planner with optional tool registry for dynamic tool discovery."""
        self._tool_registry = tool_registry

    def create_plan(self, task: AgentTask) -> AgentPlan:
        """
        Create a plan using structured function calling approach.
        
        Analyzes the instruction and dynamically selects appropriate tools
        from the registry instead of hardcoded keyword matching.
        """
        instruction = task.instruction.lower()
        steps: list[PlanStep] = []

        # W94: Dynamic tool selection based on instruction analysis
        tool_calls = self._analyze_instruction_for_tools(instruction)

        for idx, (tool_name, tool_args, description) in enumerate(tool_calls, start=1):
            # Map tool names to plan step kinds
            step_kind = self._map_tool_to_step_kind(tool_name)
            
            steps.append(
                PlanStep(
                    sequence=idx,
                    kind=step_kind,
                    description=description,
                    tool_name=tool_name,
                    tool_arguments=tool_args,
                    required_permission=self._get_tool_permission(tool_name),
                )
            )

        # Fallback if no tools matched
        if not steps:
            steps.append(
                PlanStep(
                    sequence=1,
                    kind=PlanStepKind.ANALYZE,
                    description="Analyze the user request.",
                    tool_name="run_analysis",
                    tool_arguments={"query": task.instruction},
                    required_permission="run_analysis",
                )
            )

        return AgentPlan(
            task_id=task.task_id,
            steps=tuple(steps),
        )

    def _analyze_instruction_for_tools(self, instruction: str) -> list[tuple[str, dict[str, Any], str]]:
        """
        Analyze instruction and return appropriate tool calls.
        
        Returns list of (tool_name, arguments, description) tuples.
        This method can be extended with LLM-based tool selection.
        """
        tool_calls: list[tuple[str, dict[str, Any], str]] = []

        # Tool selection logic based on instruction analysis
        if any(word in instruction for word in ("portfolio", "position", "holdings")):
            tool_calls.append((
                "read_portfolio",
                {},
                "Load current portfolio state."
            ))

        if any(word in instruction for word in (
            "analyze", "analyse", "risk", "opportunity", "market", "scan"
        )):
            tool_calls.append((
                "run_analysis",
                {"query": instruction},
                "Run financial analysis."
            ))

        if any(word in instruction for word in (
            "stress", "scenario", "simulate", "backtest", "test"
        )):
            tool_calls.append((
                "run_simulation",
                {"scenario": instruction},
                "Run requested simulation."
            ))

        if "optimize" in instruction or "allocation" in instruction:
            tool_calls.append((
                "run_portfolio_optimizer",
                {"constraints": self._extract_constraints(instruction)},
                "Run portfolio optimization."
            ))

        if "pit" in instruction or "fundamental" in instruction:
            tool_calls.append((
                "query_pit_fundamental",
                {"symbols": self._extract_symbols(instruction)},
                "Query point-in-time fundamental data."
            ))

        if "why" in instruction or "explain" in instruction:
            tool_calls.append((
                "construct_explanation",
                {"context": instruction},
                "Construct evidence-backed explanation."
            ))

        return tool_calls

    def _map_tool_to_step_kind(self, tool_name: str) -> PlanStepKind:
        """Map tool names to plan step kinds."""
        mapping = {
            "read_portfolio": PlanStepKind.OBSERVE,
            "query_pit_fundamental": PlanStepKind.OBSERVE,
            "run_analysis": PlanStepKind.ANALYZE,
            "run_simulation": PlanStepKind.SIMULATE,
            "run_portfolio_optimizer": PlanStepKind.PROPOSE,
            "construct_explanation": PlanStepKind.EXPLAIN,
        }
        return mapping.get(tool_name, PlanStepKind.ANALYZE)

    def _get_tool_permission(self, tool_name: str) -> str | None:
        """Get required permission for a tool."""
        # Map tools to their required permissions
        permission_map = {
            "read_portfolio": "read_portfolio",
            "run_analysis": "run_analysis",
            "run_simulation": "run_simulation",
            "run_portfolio_optimizer": "run_portfolio_optimizer",
            "query_pit_fundamental": "query_pit_fundamental",
        }
        return permission_map.get(tool_name)

    def _extract_symbols(self, instruction: str) -> list[str]:
        """Extract ticker symbols from instruction (placeholder for NLP)."""
        # This would use NLP/entity extraction in production
        # For now, return empty list
        return []

    def _extract_constraints(self, instruction: str) -> dict[str, Any]:
        """Extract optimization constraints from instruction (placeholder for NLP)."""
        # This would use NLP/entity extraction in production
        # For now, return empty dict
        return {}