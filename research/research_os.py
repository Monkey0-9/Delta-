"""P6/P7 — Agentic Quant Research + Research Operating System (W134/W136-W139).

Agent hierarchy: DATA/ALPHA/RISK -> EXPERIMENT -> VALIDATION -> REVIEW -> REGISTRY.
LLM proposes; deterministic system validates; authorization layer decides.
Every experiment: EXP-0000001 with dataset/features/alpha/model/params/commit/
seed/windows/cost/execution/risk/results/stats/stress/author/parent.
Lineage graph: Dataset->Feature->Alpha->Model->Experiment->Backtest->
Validation->Paper->Shadow->Production.

W136: research memory graph (vector+graph provenance).
W137: large experiment scheduler. W138: model registry.
W139: automated promotion gates.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from typing import Literal

Role = Literal["DATA", "ALPHA", "RISK", "EXPERIMENT", "VALIDATION", "REVIEW", "REGISTRY"]


def _hash(obj: object) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()[:12]


@dataclass(frozen=True, slots=True)
class Proposal:
    agent_role: Role
    hypothesis: str
    payload_hash: str
    author: str


@dataclass(frozen=True, slots=True)
class ValidationVerdict:
    passed: bool
    checks: tuple[str, ...]
    reason: str


@dataclass(frozen=True, slots=True)
class Authorization:
    allowed: bool
    actor: str
    permission: str
    reason: str


class DeterministicValidator:
    """The deterministic system that validates every LLM proposal."""

    def validate(self, p: Proposal, *, evidence: dict | None = None) -> ValidationVerdict:
        checks: list[str] = []
        ev = evidence or {}
        ok = True
        reasons: list[str] = []
        # 1. schema: hypothesis non-empty, hash present
        if p.hypothesis.strip() and p.payload_hash:
            checks.append("schema")
        else:
            ok, reasons = False, reasons + ["schema"]
        # 2. PIT discipline flag must be true
        if ev.get("pit_disciplined", False):
            checks.append("pit")
        else:
            ok = False
            reasons.append("pit")
        # 3. cost model attached
        if ev.get("cost_model"):
            checks.append("cost")
        else:
            ok = False
            reasons.append("cost")
        # 4. risk limits present
        if ev.get("risk_limits_ok", False):
            checks.append("risk")
        else:
            ok = False
            reasons.append("risk")
        return ValidationVerdict(ok, tuple(checks), ";".join(reasons) or "all checks passed")


class AuthorizationLayer:
    """Only explicitly permissioned actors can promote; agents can never self-promote."""

    _PERMS: dict[str, set[str]] = {
        "researcher": {"propose", "run_experiment"},
        "reviewer": {"propose", "approve_validation"},
        "risk_owner": {"approve_production", "rollback"},
        "system": {"promote", "rollback"},
    }

    def decide(self, actor_role: str, permission: str, verdict: ValidationVerdict) -> Authorization:
        allowed_perms = self._PERMS.get(actor_role, set())
        if permission not in allowed_perms:
            return Authorization(False, actor_role, permission, "role lacks permission")
        if permission in ("approve_production", "promote") and not verdict.passed:
            return Authorization(False, actor_role, permission, "validation failed: fail-closed")
        return Authorization(True, actor_role, permission, "granted")


@dataclass(frozen=True, slots=True)
class ExperimentRecord:
    experiment_id: str
    dataset: str
    features: str
    alpha: str
    model: str
    parameters: str
    code_commit: str
    seed: int
    train_window: str
    validation_window: str
    oos_window: str
    cost_model: str
    execution_model: str
    risk_model: str
    results: str
    stats: str
    stress: str
    author: str
    parent: str = ""


class LineageGraph:
    """DAG of research artifacts with provenance."""

    def __init__(self) -> None:
        self._nodes: dict[str, str] = {}  # id -> kind
        self._edges: dict[str, list[str]] = {}

    def add(self, node_id: str, kind: str, parents: list[str] | None = None) -> None:
        self._nodes[node_id] = kind
        for p in parents or []:
            self._edges.setdefault(p, []).append(node_id)

    def lineage(self, node_id: str) -> list[str]:
        # reverse BFS to roots (deterministic order)
        rev: dict[str, list[str]] = {}
        for p, children in self._edges.items():
            for c in children:
                rev.setdefault(c, []).append(p)
        out, stack, seen = [], [node_id], set()
        while stack:
            n = stack.pop()
            if n in seen:
                continue
            seen.add(n)
            out.append(n)
            stack.extend(sorted(rev.get(n, [])))
        return sorted(out)

    def children(self, node_id: str) -> list[str]:
        return sorted(self._edges.get(node_id, []))


@dataclass
class MemoryNode:
    node_id: str
    kind: str
    embedding: list[float]
    meta: str = ""


class ResearchMemoryGraph:
    """W136: vector + graph provenance memory."""

    def __init__(self) -> None:
        self._nodes: dict[str, MemoryNode] = {}
        self._links: dict[str, list[str]] = {}

    def store(self, node: MemoryNode, parents: list[str] | None = None) -> None:
        self._nodes[node.node_id] = node
        for p in parents or []:
            self._links.setdefault(p, []).append(node.node_id)

    def cosine(self, a: list[float], b: list[float]) -> float:
        num = sum(x * y for x, y in zip(a, b))
        da = math.sqrt(sum(x * x for x in a))
        db = math.sqrt(sum(y * y for y in b))
        return num / (da * db) if da and db else 0.0

    def recall(self, query: list[float], top_k: int = 3) -> list[str]:
        ranked = sorted(self._nodes, key=lambda nid: self.cosine(query, self._nodes[nid].embedding), reverse=True)
        return ranked[:top_k]

    def provenance(self, node_id: str) -> list[str]:
        rev: dict[str, list[str]] = {}
        for p, ch in self._links.items():
            for c in ch:
                rev.setdefault(c, []).append(p)
        out, stack, seen = [], [node_id], set()
        while stack:
            n = stack.pop()
            if n in seen:
                continue
            seen.add(n)
            out.append(n)
            stack.extend(sorted(rev.get(n, [])))
        return sorted(out)


@dataclass
class ScheduledJob:
    job_id: str
    experiment_id: str
    priority: int
    seed: int
    status: str = "queued"  # queued|running|done|failed


class ExperimentScheduler:
    """W137: deterministic priority scheduler for large experiment sweeps."""

    def __init__(self) -> None:
        self._jobs: list[ScheduledJob] = []

    def submit(self, job: ScheduledJob) -> None:
        self._jobs.append(job)

    def next_batch(self, k: int) -> list[ScheduledJob]:
        q = sorted([j for j in self._jobs if j.status == "queued"],
                   key=lambda j: (-j.priority, j.job_id))
        batch = q[:k]
        for j in batch:
            j.status = "running"
        return batch

    def complete(self, job_id: str, ok: bool = True) -> None:
        for j in self._jobs:
            if j.job_id == job_id:
                j.status = "done" if ok else "failed"


@dataclass(frozen=True, slots=True)
class ModelVersion:
    model_id: str
    version: str
    stage: str  # research|paper|shadow|production|retired
    gate_hash: str


class ModelRegistry:
    """W138: staged model registry with promotion history."""

    VALID = ("research", "paper", "shadow", "production", "retired")

    def __init__(self) -> None:
        self._models: dict[str, ModelVersion] = {}
        self._history: list[str] = []

    def register(self, m: ModelVersion) -> None:
        if m.stage not in self.VALID:
            raise ValueError("bad stage")
        self._models[f"{m.model_id}@{m.version}"] = m
        self._history.append(f"register {m.model_id}@{m.version} -> {m.stage}")

    def promote(self, model_id: str, version: str, to: str, gate_hash: str) -> ModelVersion:
        key = f"{model_id}@{version}"
        cur = self._models[key]
        order = list(self.VALID)
        if order.index(to) < order.index(cur.stage) and to != "retired":
            raise ValueError("no demotion except retire")
        nxt = ModelVersion(model_id, version, to, gate_hash)
        self._models[key] = nxt
        self._history.append(f"promote {key} {cur.stage}->{to} [{gate_hash}]")
        return nxt

    def get(self, model_id: str, version: str) -> ModelVersion:
        return self._models[f"{model_id}@{version}"]
