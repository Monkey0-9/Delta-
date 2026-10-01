"""DELTA canonical AI runtime (Phase 1).

Single source of truth for intelligence contracts. Legacy stacks
(agent/, agents/, models/, finance_model/, decision/, research/agent/,
research/real_loop/, trader/, world_model/, memory/) remain as explicitly
marked adapters until migrated; production code must route through here.
A CI test enforces that certified paths import these contracts.
"""
from ai.contracts import (
    AgentMessage,
    AgentPlan,
    AgentRole,
    AgentRun,
    AgentSpec,
    AgentTask,
    Budget,
    Claim,
    ClaimVerdict,
    DecisionRecord,
    Evidence,
    EvidenceLedger,
    EvidenceRef,
    Forecast,
    KnowledgeType,
    MessageType,
    PromotionDecision,
    ResearchSpec,
    RiskClass,
    RunStatus,
    ToolCall,
    ToolDefinition,
    ToolResult,
    ValidationProtocol,
)
from ai.executor import TypedToolExecutor, ExecutorResult
from ai.verifier import ClaimVerifier, VerificationOutcome
from ai.registry import ModelRecord, ModelRegistry
from ai.gateway import (ModelUnavailable, GenerationRequest,
                        GenerationResult, CanonicalGateway)

__all__ = [
    "AgentMessage",
    "AgentPlan",
    "AgentRole",
    "AgentRun",
    "AgentSpec",
    "AgentTask",
    "Budget",
    "Claim",
    "ClaimVerdict",
    "DecisionRecord",
    "Evidence",
    "EvidenceLedger",
    "EvidenceRef",
    "Forecast",
    "KnowledgeType",
    "MessageType",
    "PromotionDecision",
    "ResearchSpec",
    "RiskClass",
    "RunStatus",
    "ToolCall",
    "ToolDefinition",
    "ToolResult",
    "ValidationProtocol",
    "TypedToolExecutor",
    "ExecutorResult",
    "ClaimVerifier",
    "VerificationOutcome",
    "ModelRecord",
    "ModelRegistry",
    "ModelUnavailable",
    "GenerationRequest",
    "GenerationResult",
    "CanonicalGateway",
]
