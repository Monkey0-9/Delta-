"""Canonical model gateway (Phase 3).

Per-role model mapping (never a global switch), capability-routed
generation, structured-output validation, and full provenance. Provider
calls are injected — the gateway never invents model text.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Mapping
from uuid import UUID, uuid4

from ai.registry import ModelRecord, ModelRegistry


class ModelUnavailable(Exception):
    pass


@dataclass(frozen=True, slots=True)
class GenerationRequest:
    request_id: UUID = field(default_factory=uuid4)
    task_id: UUID = field(default_factory=uuid4)
    role: str = "commentary"
    messages: tuple[Mapping[str, Any], ...] = ()
    required_capabilities: frozenset[str] = frozenset()
    response_schema: Mapping[str, Any] = field(default_factory=dict)
    tool_definitions: tuple[Mapping[str, Any], ...] = ()
    temperature: float = 0.0
    max_tokens: int = 2000
    timeout_ms: int = 30_000
    latency_budget_ms: float = 10_000.0
    cost_budget: float = 1.0
    context_needed: int = 4000
    high_risk: bool = True
    trace_id: str = ""


@dataclass(frozen=True, slots=True)
class GenerationResult:
    request_id: UUID
    model_id: str
    model_version: str
    text: str = ""
    structured_output: Mapping[str, Any] | None = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: float = 0.0
    finish_reason: str = ""
    provider: str = ""
    errors: tuple[str, ...] = ()
    provenance: Mapping[str, Any] = field(default_factory=dict)


def _validate_structured(output: Any,
                         schema: Mapping[str, Any]) -> tuple[bool, str]:
    if not schema:
        return True, "ok"
    if not isinstance(output, Mapping):
        return False, "structured output must be an object"
    for req in schema.get("required", []):
        if req not in output:
            return False, f"missing required field: {req}"
    return True, "ok"


class CanonicalGateway:
    """Role-isolated gateway over a capability-verified registry."""

    def __init__(self, registry: ModelRegistry,
                 generate_fn: Callable[[ModelRecord, GenerationRequest], Mapping[str, Any]] | None = None) -> None:
        self._registry = registry
        self._generate_fn = generate_fn
        self._roles: dict[str, str] = {}

    def use_for(self, role: str, model_id: str) -> str:
        """Pin one role to a model. Roles are independent — no global switch."""
        if model_id not in [r.model_id for r in self._registry.list()]:
            raise ModelUnavailable(f"unknown model {model_id!r}")
        self._roles[role] = model_id
        return model_id

    def model_for(self, role: str) -> str | None:
        return self._roles.get(role)

    def generate(self, request: GenerationRequest) -> GenerationResult:
        pinned = self._roles.get(request.role)
        if pinned is not None:
            recs = [r for r in self._registry.list() if r.model_id == pinned]
            if not recs:
                raise ModelUnavailable(f"pinned model {pinned!r} not registered")
            rec = recs[0]
            missing = set(request.required_capabilities) - set(rec.capabilities)
            if missing:
                raise ModelUnavailable(
                    f"pinned {pinned!r} lacks capabilities {sorted(missing)}")
            if request.high_risk and not rec.verified:
                raise ModelUnavailable(f"pinned {pinned!r} unverified for high-risk role")
        else:
            try:
                rec = self._registry.route(
                    request.required_capabilities,
                    latency_budget_ms=request.latency_budget_ms,
                    cost_budget=request.cost_budget,
                    context_needed=request.context_needed,
                    high_risk=request.high_risk)
            except LookupError as exc:
                raise ModelUnavailable(str(exc)) from exc
        if self._generate_fn is None:
            raise ModelUnavailable(
                f"no provider wired for {rec.model_id!r}; refusing to invent text")
        import time
        start = time.perf_counter_ns()
        try:
            raw = dict(self._generate_fn(rec, request))
        except ModelUnavailable:
            raise
        except Exception as exc:
            raise ModelUnavailable(f"provider {rec.model_id!r} failed: {exc}") from exc
        dt_ms = (time.perf_counter_ns() - start) / 1e6
        structured = raw.get("structured_output")
        if request.response_schema:
            ok, msg = _validate_structured(structured, request.response_schema)
            if not ok:
                raise ModelUnavailable(f"schema validation failed: {msg}")
        return GenerationResult(
            request_id=request.request_id, model_id=rec.model_id,
            model_version=rec.version, text=str(raw.get("text", "")),
            structured_output=structured,
            prompt_tokens=int(raw.get("prompt_tokens", 0)),
            completion_tokens=int(raw.get("completion_tokens", 0)),
            latency_ms=dt_ms, finish_reason=str(raw.get("finish_reason", "")),
            provider=rec.provider, provenance={
                "model_id": rec.model_id, "model_version": rec.version,
                "verified": rec.verified, "role": request.role,
                "trace_id": request.trace_id,
                "at": datetime.now(timezone.utc).isoformat()})

    def health(self) -> Mapping[str, Any]:
        return {"models": [
            {"id": r.model_id, "verified": r.verified, "status": r.status}
            for r in self._registry.list()],
            "roles": dict(self._roles)}


__all__ = ["ModelUnavailable", "GenerationRequest", "GenerationResult",
           "CanonicalGateway"]
