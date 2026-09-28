"""W211-W230 (H) — Agentic research stack with explicit permission levels.

LLM -> Research Planner -> Permission Layer -> Tool Registry -> Sandbox ->
Experiment -> Validator -> Registry. LLM proposes; deterministic software
validates. Levels R0..R5; R1 can never jump to R5 without promotion gates.
"""
from __future__ import annotations

from dataclasses import dataclass, field

LEVELS: tuple[str, ...] = ("R0", "R1", "R2", "R3", "R4", "R5")
LEVEL_DESC = {"R0": "READ", "R1": "RESEARCH", "R2": "EXPERIMENT",
              "R3": "PAPER", "R4": "SHADOW", "R5": "LIVE"}

# which target levels each tool call requires
TOOL_LEVEL: dict[str, str] = {
    "read_market": "R0", "read_memory": "R0",
    "propose_hypothesis": "R1", "generate_features": "R1",
    "run_backtest": "R2", "run_experiment": "R2",
    "start_paper": "R3", "start_shadow": "R4",
    "submit_live": "R5", "promote": "R5",
}


@dataclass(frozen=True, slots=True)
class Plan:
    hypothesis: str
    tools: tuple[str, ...]
    max_level: str


class ResearchPlanner:
    """Deterministic planner: maps an LLM proposal onto an explicit tool plan."""

    def plan(self, hypothesis: str, *, intent: str = "backtest") -> Plan:
        if intent == "backtest":
            tools = ("read_market", "propose_hypothesis", "generate_features", "run_backtest")
            ml = "R2"
        elif intent == "paper":
            tools = ("read_market", "propose_hypothesis", "generate_features",
                     "run_backtest", "start_paper")
            ml = "R3"
        elif intent == "shadow":
            tools = ("read_market", "propose_hypothesis", "generate_features",
                     "run_backtest", "start_paper", "start_shadow")
            ml = "R4"
        else:
            tools = ("read_market", "propose_hypothesis")
            ml = "R1"
        return Plan(hypothesis, tools, ml)


@dataclass
class PermissionLayer:
    agent_level: str = "R1"
    promotions: list[str] = field(default_factory=list)

    def allow_tool(self, tool: str) -> tuple[bool, str]:
        need = TOOL_LEVEL.get(tool)
        if need is None:
            return False, f"unknown tool {tool}"
        if LEVELS.index(need) <= LEVELS.index(self.agent_level):
            return True, "granted"
        return False, f"requires {need}, agent at {self.agent_level}"

    def request_promotion(self, to: str, gate_passed: bool) -> tuple[bool, str]:
        if LEVELS.index(to) != LEVELS.index(self.agent_level) + 1:
            return False, "promotion must advance exactly one level (no R1->R5)"
        if not gate_passed:
            return False, "gate failed: fail-closed"
        self.agent_level = to
        self.promotions.append(to)
        return True, f"promoted to {to} ({LEVEL_DESC[to]})"


@dataclass
class ToolRegistry:
    tools: dict[str, str] = field(default_factory=dict)  # tool -> sandbox image

    def register(self, tool: str, sandbox: str) -> None:
        if tool not in TOOL_LEVEL:
            raise ValueError(f"refusing unlisted tool {tool}")
        self.tools[tool] = sandbox

    def sandbox_for(self, tool: str) -> str:
        return self.tools[tool]


@dataclass
class Sandbox:
    """Records tool executions; nothing escapes without validator approval."""

    runs: list[str] = field(default_factory=list)

    def execute(self, tool: str, payload: str, *, permission: PermissionLayer,
                registry: ToolRegistry) -> tuple[bool, str]:
        ok, reason = permission.allow_tool(tool)
        if not ok:
            return False, f"blocked: {reason}"
        try:
            image = registry.sandbox_for(tool)
        except KeyError:
            return False, f"blocked: {tool} not registered"
        self.runs.append(f"{image}:{tool}:{payload[:32]}")
        return True, "executed in sandbox"
