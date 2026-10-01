"""Research DAG executor (Phase 3).

Compiles a ResearchSpec into an ordered stage graph and runs each stage
as a typed ToolCall through the executor. Stages with no registered
tool are BLOCKED (fail-closed): the run reports PARTIAL/FAILED with the
missing stage named — never synthetic results.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping
from uuid import UUID

from ai.contracts import EvidenceLedger, ResearchSpec, RunStatus
from ai.executor import TypedToolExecutor, _BudgetState


# stage -> (tool_name, description). Tools must be registered+granted.
STAGES: tuple[tuple[str, str, str], ...] = (
    ("literature_memory", "memory_search", "Prior tests and literature"),
    ("data_pit", "fetch_pit_dataset", "PIT dataset at cutoff"),
    ("features", "build_features", "Feature graph"),
    ("baselines", "run_baselines", "Baseline models"),
    ("candidates", "fit_candidates", "Candidate models"),
    ("walkforward_oos", "walkforward_oos", "Purged walk-forward + OOS"),
    ("costs", "estimate_costs", "Transaction-cost model"),
    ("capacity", "estimate_capacity", "Capacity curve"),
    ("stress", "run_stress", "Stress scenarios"),
    ("statistics", "run_statistics", "HAC/bootstrap/DSR/PBO/reality"),
    ("critic", "critique", "Independent critique"),
    ("review", "independent_review", "Independent validation"),
    ("register", "register_experiment", "Research registry record"),
    ("shadow", "shadow_qualify", "Shadow eligibility check"),
)


@dataclass(slots=True)
class DagRun:
    spec: ResearchSpec
    status: RunStatus = RunStatus.PLANNED
    stages: list[dict[str, Any]] = field(default_factory=list)
    blocked: list[str] = field(default_factory=list)


def compile_dag(spec: ResearchSpec) -> list[dict[str, Any]]:
    """Compile spec to ordered stages with dependency edges."""
    dag: list[dict[str, Any]] = []
    prev: str | None = None
    for stage, tool, desc in STAGES:
        dag.append({"stage": stage, "tool": tool, "description": desc,
                    "depends_on": prev, "hypothesis": spec.hypothesis,
                    "validation_protocol": spec.validation_protocol.value})
        prev = stage
    return dag


def run_dag(spec: ResearchSpec, executor: TypedToolExecutor, agent_id: str,
            task_id: UUID, budget: _BudgetState | None = None,
            arguments: Mapping[str, Any] | None = None) -> DagRun:
    """Execute the DAG in order. Missing tools block; failures stop the run."""
    from ai.executor import TypedToolExecutor as _T  # noqa (type clarity)
    run = DagRun(spec=spec, status=RunStatus.RUNNING)
    args = dict(arguments or {})
    for node in compile_dag(spec):
        call_kwargs: dict[str, Any] = {
            "agent_id": agent_id, "tool_name": node["tool"],
            "arguments": {**args, "stage": node["stage"],
                          "hypothesis": spec.hypothesis},
            "task_id": task_id}
        from ai.contracts import ToolCall
        call = ToolCall(task_id=task_id, tool_name=node["tool"],
                        arguments=call_kwargs["arguments"],
                        requested_by=agent_id)
        if node["tool"] not in getattr(executor, "_defs", {}):
            run.stages.append({**node, "status": "blocked",
                               "reason": f"tool {node['tool']!r} not registered"})
            run.blocked.append(node["stage"])
            run.status = RunStatus.FAILED
            return run
        res = executor.execute(call, agent_id, budget=budget)
        run.stages.append({**node, "status": res.status,
                           "error": res.error,
                           "evidence_refs": list(res.evidence_refs)})
        if res.status != "ok":
            run.status = RunStatus.PARTIAL if run.stages[:-1] else RunStatus.FAILED
            run.blocked.append(node["stage"])
            return run
    run.status = RunStatus.COMPLETED
    return run


__all__ = ["STAGES", "DagRun", "compile_dag", "run_dag"]
