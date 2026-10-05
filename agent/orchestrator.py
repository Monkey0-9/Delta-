"""Phases 14-15 — Agent system + execution loop. Risk-governor is deterministic.

Agents: market/portfolio/risk/macro/execution/research/data-quality/reconciliation.
Loop: CLASSIFY->RESOLVE->PLAN->TOOLS->DATA->QUANT->RISK->SYNTHESIZE->PERMISSION
->EXECUTE?->RECONCILE->AUDIT->RESPOND. Progress events only (SUMMARY/ACTIVITY).
"""
from __future__ import annotations

from dataclasses import dataclass, field


AGENTS = ("market-analyst", "portfolio-analyst", "risk-governor", "macro-analyst",
          "execution-analyst", "research-agent", "data-quality-agent",
          "reconciliation-agent")


@dataclass
class AgentSpec:
    name: str
    role: str
    model: str = ""
    effort: str = "MEDIUM"
    tools: tuple = ()
    permissions: tuple = ("READ",)
    status: str = "IDLE"
    last_action: str = ""


LOOP_STAGES = ("classify", "resolve", "plan", "tools", "data", "quant",
               "risk", "synthesize", "permission", "execute", "reconcile",
               "audit", "respond")


@dataclass
class Task:
    task_id: str
    title: str
    stage: str = "queued"  # running|queued|done|failed|cancelled
    progress: list = field(default_factory=list)


class TaskQueue:
    """Steer (Enter), queue (Alt+Enter), cancel analytical tasks via Esc.
    Staged/live orders are NEVER touched by Esc — separate confirm flow."""

    def __init__(self):
        self._tasks: dict[str, Task] = {}
        self._n = 0

    def submit(self, title: str) -> Task:
        self._n += 1
        t = Task(f"T-{self._n:04d}", title,
                 stage="running" if not self.current() else "queued")
        self._tasks[t.task_id] = t
        return t

    def current(self) -> Task | None:
        return next((t for t in self._tasks.values() if t.stage == "running"), None)

    def queued(self) -> list[Task]:
        return [t for t in self._tasks.values() if t.stage == "queued"]

    def cancel_task(self, task_id: str) -> None:
        t = self._tasks[task_id]
        if t.stage in ("running", "queued"):
            t.stage = "cancelled"


__all__ = ["AGENTS", "AgentSpec", "LOOP_STAGES", "Task", "TaskQueue"]
