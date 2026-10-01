"""Canonical model registry (Phase 3).

Capability-verified, benchmark-driven routing. The model name is an
implementation detail: tasks declare required capabilities, latency and
cost budgets, and context needs; the registry selects among VERIFIED
models. Unverified models are ineligible for high-risk roles.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Mapping


@dataclass(frozen=True, slots=True)
class ModelRecord:
    model_id: str
    version: str = "v1"
    provider: str = "local"
    capabilities: frozenset[str] = frozenset()
    max_context: int = 8000
    latency_ms_p50: float = 1000.0
    cost_per_1k: float = 0.0
    quality: Mapping[str, float] = field(default_factory=dict)
    verified: bool = False
    verified_at: str = ""
    status: str = "EXPERIMENTAL"

    def __post_init__(self) -> None:
        if not self.model_id.strip():
            raise ValueError("model_id must be non-empty")


@dataclass(slots=True)
class ModelRegistry:
    _models: dict[str, ModelRecord] = field(default_factory=dict)
    _probes: dict[str, Callable[[str], bool]] = field(default_factory=dict)

    def register(self, record: ModelRecord, overwrite: bool = False) -> None:
        if record.model_id in self._models and not overwrite:
            raise ValueError(f"model {record.model_id!r} already registered")
        self._models[record.model_id] = record

    def probe(self, model_id: str, check: Callable[[str], bool]) -> bool:
        """Run a capability probe; VERIFIED only on pass. Returns result."""
        rec = self._models.get(model_id)
        if rec is None:
            raise KeyError(f"unknown model {model_id!r}")
        try:
            ok = bool(check(model_id))
        except Exception:
            ok = False
        self._models[model_id] = ModelRecord(
            model_id=rec.model_id, version=rec.version, provider=rec.provider,
            capabilities=rec.capabilities, max_context=rec.max_context,
            latency_ms_p50=rec.latency_ms_p50, cost_per_1k=rec.cost_per_1k,
            quality=dict(rec.quality), verified=ok,
            verified_at=datetime.now(timezone.utc).isoformat()
            if ok else rec.verified_at,
            status=rec.status)
        return ok

    def route(self, required: frozenset[str] | set[str],
              latency_budget_ms: float = 10_000.0,
              cost_budget: float = 1.0,
              context_needed: int = 4000,
              min_quality: Mapping[str, float] | None = None,
              high_risk: bool = True) -> ModelRecord:
        """Select the best eligible model. Raises when none qualifies."""
        req = frozenset(required)
        cands: list[tuple[float, str, ModelRecord]] = []
        for rec in self._models.values():
            if not req <= rec.capabilities:
                continue
            if rec.latency_ms_p50 > latency_budget_ms:
                continue
            if rec.cost_per_1k > cost_budget:
                continue
            if rec.max_context < context_needed:
                continue
            if high_risk and not rec.verified:
                continue
            if min_quality:
                if any(rec.quality.get(k, 0.0) < v for k, v in min_quality.items()):
                    continue
            score = sum(rec.quality.values())
            cands.append((score, rec.model_id, rec))
        if not cands:
            raise LookupError(
                f"no eligible model for capabilities={sorted(req)} "
                f"(latency<={latency_budget_ms}ms cost<={cost_budget} "
                f"context>={context_needed} high_risk={high_risk})")
        cands.sort(key=lambda t: (-t[0], t[1]))
        return cands[0][2]

    def list(self) -> tuple[ModelRecord, ...]:
        return tuple(sorted(self._models.values(), key=lambda r: r.model_id))


__all__ = ["ModelRecord", "ModelRegistry"]
