from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

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
    required_permission: str | None = None


@dataclass(frozen=True, slots=True)
class AgentPlan:
    task_id: UUID
    steps: tuple[PlanStep, ...]


class AgentPlanner:
    """
    Deterministic baseline planner.

    A model-backed planner can later replace this component,
    but the resulting plan still passes through policy validation.
    """

    def create_plan(self, task: AgentTask) -> AgentPlan:
        instruction = task.instruction.lower()

        steps: list[PlanStep] = []

        if "portfolio" in instruction:
            steps.append(
                PlanStep(
                    1,
                    PlanStepKind.OBSERVE,
                    "Load current portfolio state.",
                    "read_portfolio",
                )
            )

        if any(word in instruction for word in (
            "analyze",
            "analyse",
            "risk",
            "opportunity",
            "market",
        )):
            steps.append(
                PlanStep(
                    len(steps) + 1,
                    PlanStepKind.ANALYZE,
                    "Run financial analysis.",
                    "run_analysis",
                )
            )

        if any(word in instruction for word in (
            "stress",
            "scenario",
            "simulate",
            "backtest",
        )):
            steps.append(
                PlanStep(
                    len(steps) + 1,
                    PlanStepKind.SIMULATE,
                    "Run requested simulation.",
                    "run_simulation",
                )
            )

        if "why" in instruction or "explain" in instruction:
            steps.append(
                PlanStep(
                    len(steps) + 1,
                    PlanStepKind.EXPLAIN,
                    "Construct evidence-backed explanation.",
                    None,
                )
            )

        if not steps:
            steps.append(
                PlanStep(
                    1,
                    PlanStepKind.ANALYZE,
                    "Analyze the user request.",
                    "run_analysis",
                )
            )

        return AgentPlan(
            task_id=task.task_id,
            steps=tuple(steps),
        )