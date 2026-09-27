from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

TOOL_ALLOWLIST: tuple[str, ...] = (
    "world_state.read",
    "quant.read",
    "portfolio.read",
    "risk.read",
    "evidence.read",
)

MAX_CONTEXT_TOKENS = 8192


@dataclass(frozen=True, slots=True)
class ModelSpec:
    name: str
    context_tokens: int
    tools: tuple[str, ...] = TOOL_ALLOWLIST


@dataclass(frozen=True, slots=True)
class RoutingDecision:
    model: str
    prompt_version: str
    truncated: bool
    reason: str


class LocalRouter:
    """Local/open-model router: complexity-based selection, 8k cap, tool gate.

    No broker tools are ever routable (hard invariant). Long contexts are
    deterministically truncated head+tail with a marker so grounding stays
    reproducible.
    """

    def __init__(self, models: tuple[ModelSpec, ...] | None = None) -> None:
        self._models = models or (
            ModelSpec("delta-local-small", 4096),
            ModelSpec("delta-local-large", 8192),
        )

    def route(self, *, complexity: Decimal, tokens: int, tool: str) -> RoutingDecision:
        if tool not in TOOL_ALLOWLIST:
            raise ValueError(f"tool not allowed: {tool}")
        if tokens < 0:
            raise ValueError("tokens cannot be negative.")
        model = self._models[0]
        reason = "simple query -> small model"
        if complexity > Decimal("0.6") or tokens > self._models[0].context_tokens:
            model = self._models[-1]
            reason = "complex/long context -> large model"
        truncated = tokens > MAX_CONTEXT_TOKENS
        if tokens > model.context_tokens:
            raise ValueError(
                f"context {tokens} exceeds {model.name} cap {model.context_tokens}."
            )
        return RoutingDecision(model.name, "v1", truncated, reason)

    @staticmethod
    def truncate(text: str, max_tokens: int = MAX_CONTEXT_TOKENS) -> str:
        if max_tokens <= 0:
            raise ValueError("max_tokens must be positive.")
        # ~4 chars per token heuristic, deterministic head+tail split.
        max_chars = max_tokens * 4
        if len(text) <= max_chars:
            return text
        head = max_chars * 3 // 4
        tail = max_chars - head - len("\n...[truncated]...\n")
        return text[:head] + "\n...[truncated]...\n" + text[len(text) - tail:]
