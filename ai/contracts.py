"""Canonical AI contracts for DELTA (Phase 1).

One typed vocabulary for tools, evidence, agents, forecasts, decisions,
and promotion. All promotion/certification paths must use these types.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import StrEnum
from typing import Any, Mapping
from uuid import UUID, uuid4
import hashlib
import json


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _hash(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(dict(payload), sort_keys=True, default=str).encode()
    ).hexdigest()[:16]


class RiskClass(StrEnum):
    READ_ONLY = "read_only"
    SIMULATION = "simulation"
    RESEARCH_WRITE = "research_write"
    CRITICAL = "critical"


class RunStatus(StrEnum):
    PLANNED = "planned"
    RUNNING = "running"
    WAITING = "waiting"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"
    ABORTED = "aborted"
    CANCELLED = "cancelled"


class ClaimVerdict(StrEnum):
    SUPPORTED = "supported"
    CONTRADICTED = "contradicted"
    UNSUPPORTED = "unsupported"
    STALE = "stale"
    TEMPORALLY_INVALID = "temporally_invalid"


class KnowledgeType(StrEnum):
    OBSERVATION = "observation"
    FACT = "fact"
    HYPOTHESIS = "hypothesis"
    MODEL_OUTPUT = "model_output"
    INTERPRETATION = "interpretation"
    VALIDATED_RESULT = "validated_result"
    FAILURE = "failure"
    LESSON_CANDIDATE = "lesson_candidate"


class ValidationProtocol(StrEnum):
    PURGED_WALK_FORWARD = "purged_walk_forward"
    CHRONOLOGICAL_HOLDOUT = "chronological_holdout"
    GENERIC_CV_FORBIDDEN = "generic_cv_forbidden"


class AgentRole(StrEnum):
    INTENT = "intent"
    PLANNER = "planner"
    MARKET = "market"
    MACRO = "macro"
    NEWS = "news"
    FUNDAMENTAL = "fundamental"
    QUANT = "quant"
    FORECAST = "forecast"
    REGIME = "regime"
    PORTFOLIO = "portfolio"
    RISK = "risk"
    EXECUTION_ANALYSIS = "execution_analysis"
    CRITIC = "critic"
    VALIDATOR = "validator"
    MEMORY = "memory"
    OPERATIONS = "operations"


class MessageType(StrEnum):
    OBSERVATION = "observation"
    REQUEST = "request"
    PLAN = "plan"
    TOOL_REQUEST = "tool_request"
    TOOL_RESULT = "tool_result"
    FINDING = "finding"
    FORECAST = "forecast"
    RISK_ASSESSMENT = "risk_assessment"
    DECISION_CANDIDATE = "decision_candidate"
    CRITIQUE = "critique"
    VALIDATION = "validation"
    REJECTION = "rejection"
    APPROVAL = "approval"


@dataclass(frozen=True, slots=True)
class Budget:
    max_steps: int = 20
    max_tool_calls: int = 50
    timeout_s: float = 120.0
    max_tokens: int = 16000
    max_cost_usd: float = 1.0
    max_retries: int = 2

    def __post_init__(self) -> None:
        if self.max_steps <= 0 or self.max_tool_calls <= 0:
            raise ValueError("budget steps/calls must be positive")
        if self.timeout_s <= 0 or self.max_tokens <= 0:
            raise ValueError("budget timeout/tokens must be positive")


@dataclass(frozen=True, slots=True)
class ToolDefinition:
    """Canonical tool declaration. No free-text tool syntax allowed."""

    name: str
    description: str = ""
    input_schema: Mapping[str, Any] = field(default_factory=dict)
    output_schema: Mapping[str, Any] = field(default_factory=dict)
    permission: str = ""
    risk_class: RiskClass = RiskClass.READ_ONLY
    side_effect: bool = False
    data_scope: tuple[str, ...] = ()
    asset_scope: tuple[str, ...] = ()
    account_scope: tuple[str, ...] = ()
    timeout_ms: int = 30_000
    max_calls: int = 10
    idempotency_required: bool = False

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            raise ValueError("tool name must be non-empty")
        if self.risk_class == RiskClass.CRITICAL and not self.side_effect:
            raise ValueError("CRITICAL tools must declare side_effect=True")


@dataclass(frozen=True, slots=True)
class ToolCall:
    call_id: UUID = field(default_factory=uuid4)
    task_id: UUID = field(default_factory=uuid4)
    tool_name: str = ""
    arguments: Mapping[str, Any] = field(default_factory=dict)
    parent_call_id: UUID | None = None
    requested_by: str = ""
    idempotency_key: str = ""

    def __post_init__(self) -> None:
        if not self.tool_name.strip():
            raise ValueError("tool_name must be non-empty")


@dataclass(frozen=True, slots=True)
class ToolResult:
    call_id: UUID
    status: str = "ok"  # ok | error | denied | timeout
    data: Any = None
    evidence_refs: tuple[str, ...] = ()
    started_at: datetime = field(default_factory=_utcnow)
    completed_at: datetime = field(default_factory=_utcnow)
    latency_ms: float = 0.0
    error: str | None = None


@dataclass(frozen=True, slots=True)
class EvidenceRef:
    evidence_id: str
    hash: str = ""


@dataclass(frozen=True, slots=True)
class Evidence:
    """One retrievable fact with provenance. External text is data, never instruction."""

    evidence_id: str
    source: str
    payload: Mapping[str, Any] = field(default_factory=dict)
    published_at: datetime | None = None
    available_at: datetime | None = None
    retrieved_at: datetime = field(default_factory=_utcnow)
    knowledge_type: KnowledgeType = KnowledgeType.OBSERVATION
    confidence: float = 1.0
    authority: str = ""
    hash: str = ""

    def __post_init__(self) -> None:
        if not self.evidence_id.strip():
            raise ValueError("evidence_id must be non-empty")
        if self.hash == "":
            object.__setattr__(self, "hash", _hash(
                {"id": self.evidence_id, "source": self.source,
                 "payload": dict(self.payload)}))

    def ref(self) -> EvidenceRef:
        return EvidenceRef(self.evidence_id, self.hash)


@dataclass(frozen=True, slots=True)
class Claim:
    claim_id: str
    text: str
    evidence_refs: tuple[str, ...] = ()
    numeric_assertions: tuple[tuple[str, float, float], ...] = ()
    # (field_path, expected_value, tolerance)
    decision_at: datetime | None = None


@dataclass(slots=True)
class EvidenceLedger:
    """Append-only record of tool executions and evidence produced."""

    entries: list[dict[str, Any]] = field(default_factory=list)

    def record_tool(self, call: ToolCall, result: ToolResult) -> None:
        self.entries.append({
            "kind": "tool",
            "call_id": str(call.call_id),
            "task_id": str(call.task_id),
            "tool": call.tool_name,
            "status": result.status,
            "evidence_refs": list(result.evidence_refs),
            "latency_ms": result.latency_ms,
            "at": _utcnow().isoformat(),
        })

    def record_claim(self, claim: Claim, verdict: ClaimVerdict, detail: str) -> None:
        self.entries.append({
            "kind": "claim",
            "claim_id": claim.claim_id,
            "verdict": verdict.value,
            "detail": detail,
            "at": _utcnow().isoformat(),
        })


@dataclass(frozen=True, slots=True)
class AgentSpec:
    agent_id: str
    role: AgentRole
    objective: str = ""
    required_capabilities: tuple[str, ...] = ()
    allowed_tools: tuple[str, ...] = ()
    allowed_data: tuple[str, ...] = ()
    forbidden_actions: tuple[str, ...] = ()
    output_schema: Mapping[str, Any] = field(default_factory=dict)
    budget: Budget = field(default_factory=Budget)

    def __post_init__(self) -> None:
        if not self.agent_id.strip():
            raise ValueError("agent_id must be non-empty")


@dataclass(frozen=True, slots=True)
class AgentTask:
    task_id: UUID = field(default_factory=uuid4)
    instruction: str = ""
    created_at: datetime = field(default_factory=_utcnow)

    def __post_init__(self) -> None:
        if not self.instruction.strip():
            raise ValueError("instruction must be non-empty")


@dataclass(frozen=True, slots=True)
class AgentPlan:
    task_id: UUID
    steps: tuple[ToolCall, ...] = ()


@dataclass(frozen=True, slots=True)
class AgentMessage:
    message_id: UUID = field(default_factory=uuid4)
    task_id: UUID = field(default_factory=uuid4)
    sender: str = ""
    recipient: str = ""
    message_type: MessageType = MessageType.OBSERVATION
    payload: Mapping[str, Any] = field(default_factory=dict)
    evidence_refs: tuple[str, ...] = ()
    state_version: str = ""
    model_version: str = ""
    created_at: datetime = field(default_factory=_utcnow)


@dataclass(frozen=True, slots=True)
class AgentRun:
    run_id: UUID = field(default_factory=uuid4)
    task_id: UUID = field(default_factory=uuid4)
    agent_id: str = ""
    status: RunStatus = RunStatus.PLANNED
    steps_executed: int = 0
    tool_calls: int = 0
    ledger_hash: str = ""
    detail: str = ""


@dataclass(frozen=True, slots=True)
class Forecast:
    """Probabilistic forecast — distributions, never point-price primacy."""

    instrument: str
    horizon: str
    mean_return: float = 0.0
    median_return: float = 0.0
    q05: float = 0.0
    q25: float = 0.0
    q50: float = 0.0
    q75: float = 0.0
    q95: float = 0.0
    probability_positive: float = 0.5
    volatility: float = 0.0
    data_uncertainty: float = 0.0
    model_uncertainty: float = 0.0
    regime_uncertainty: float = 0.0
    execution_uncertainty: float = 0.0
    calibration_score: float | None = None
    model_version: str = ""
    state_version: str = ""

    def __post_init__(self) -> None:
        if not (self.q05 <= self.q25 <= self.q50 <= self.q75 <= self.q95):
            raise ValueError("forecast quantiles must be ordered")
        if not 0.0 <= self.probability_positive <= 1.0:
            raise ValueError("probability_positive must be in [0,1]")


@dataclass(frozen=True, slots=True)
class ResearchSpec:
    """DAG-compilable research specification. No fixed pipeline."""

    hypothesis: str
    universe: tuple[str, ...] = ()
    horizon: str = ""
    target: str = ""
    benchmark: str = ""
    data_requirements: tuple[str, ...] = ()
    pit_cutoff: datetime | None = None
    features: tuple[str, ...] = ()
    controls: tuple[str, ...] = ()
    model_candidates: tuple[str, ...] = ()
    baselines: tuple[str, ...] = ()
    validation_protocol: ValidationProtocol = ValidationProtocol.PURGED_WALK_FORWARD
    transaction_cost_model: str = ""
    capacity_model: str = ""
    stress_scenarios: tuple[str, ...] = ()
    multiple_testing_policy: str = ""
    promotion_policy: str = ""

    def __post_init__(self) -> None:
        if not self.hypothesis.strip():
            raise ValueError("hypothesis must be non-empty")
        if self.validation_protocol == ValidationProtocol.GENERIC_CV_FORBIDDEN:
            raise ValueError("generic CV is forbidden for research validation")


@dataclass(frozen=True, slots=True)
class DecisionRecord:
    """Answerable later: why, what was known, which model, what changed."""

    decision_id: str
    user_intent: str = ""
    mandate_hash: str = ""
    world_state_version: str = ""
    market_data_hash: str = ""
    feature_version: str = ""
    forecast_version: str = ""
    regime_version: str = ""
    portfolio_version: str = ""
    risk_version: str = ""
    model_versions: tuple[tuple[str, str], ...] = ()
    prompt_version: str = ""
    evidence_refs: tuple[str, ...] = ()
    candidate_actions: tuple[str, ...] = ()
    selected_action: str = ""
    reason_codes: tuple[str, ...] = ()
    uncertainties: tuple[tuple[str, float], ...] = ()
    critic_result: str = ""
    validator_result: str = ""
    authorization: str = ""
    execution_mode: str = ""
    created_at: datetime = field(default_factory=_utcnow)


@dataclass(frozen=True, slots=True)
class PromotionDecision:
    """Evidence, never a boolean. Every promotion is auditable."""

    agent_id: str = ""
    model_id: str = ""
    from_level: str = ""
    to_level: str = ""
    gate_results: tuple[tuple[str, str, str], ...] = ()
    # (gate, status, evidence_ref)
    reviewer: str = ""
    model_version: str = ""
    policy_version: str = ""
    experiment_ids: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    created_at: datetime = field(default_factory=_utcnow)

    def __post_init__(self) -> None:
        if not self.experiment_ids:
            raise ValueError("promotion requires experiment_ids")
        if not self.gate_results:
            raise ValueError("promotion requires gate_results")
        bad = [g for g, s, _ in self.gate_results if s != "PASS"]
        if bad:
            raise ValueError(f"non-PASS gates block promotion: {bad}")


__all__ = [
    "Budget", "ToolDefinition", "ToolCall", "ToolResult",
    "EvidenceRef", "Evidence", "Claim", "ClaimVerdict", "EvidenceLedger",
    "AgentSpec", "AgentRole", "AgentTask", "AgentPlan", "AgentMessage",
    "AgentRun", "RunStatus", "MessageType", "Forecast", "ResearchSpec",
    "ValidationProtocol", "KnowledgeType", "RiskClass", "DecisionRecord",
    "PromotionDecision",
]
