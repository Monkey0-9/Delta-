"""Phases 12-13 — Runtime ModelRegistry + effort/thinking system.

Capabilities are measured/health-checked, NEVER inferred from name substrings.
Effort: LOW|MEDIUM|HIGH|XHIGH|AUTO. Thinking display: OFF|SUMMARY|ACTIVITY
(operational progress only — never private chain-of-thought).
"""
from __future__ import annotations

from dataclasses import dataclass, field


EFFORTS = ("LOW", "MEDIUM", "HIGH", "XHIGH", "AUTO")
THINKING_MODES = ("OFF", "SUMMARY", "ACTIVITY")


@dataclass
class ModelRecord:
    provider: str
    model_id: str
    version: str = ""
    status: str = "UNKNOWN"  # READY|DEGRADED|DISCONNECTED|ERROR|UNKNOWN
    latency_ms: float | None = None
    context: int = 0
    tool_support: bool = False
    streaming: bool = False
    structured_output: bool = False
    reasoning: bool = False
    cost_per_1k: float | None = None
    roles: tuple = ()


class ModelRegistry:
    def __init__(self):
        self._models: dict[str, ModelRecord] = {}
        self.active: str = ""

    def register(self, rec: ModelRecord) -> None:
        self._models[f"{rec.provider}/{rec.model_id}"] = rec

    def switch(self, key: str) -> ModelRecord:
        try:
            rec = self._models[key]
        except KeyError:
            raise ValueError(f"unknown model {key!r}")
        if rec.status != "READY":
            raise ValueError(f"model {key} not READY ({rec.status})")
        self.active = key
        return rec

    def list(self) -> list[ModelRecord]:
        return list(self._models.values())


def auto_effort(task: str) -> str:
    t = (task or "").lower()
    if any(k in t for k in ("price?", "quote", "status", "lookup")):
        return "LOW"
    if any(k in t for k in ("hedge", "design a", "regime-aware", "critique")):
        return "XHIGH"
    if any(k in t for k in ("compare", "optimiz", "stress", "cross-asset", "risk")):
        return "HIGH"
    return "MEDIUM"


def thinking_steps() -> list[str]:
    return ["resolve instrument", "portfolio", "market data", "risk", "completed"]


__all__ = ["EFFORTS", "THINKING_MODES", "ModelRecord", "ModelRegistry",
           "auto_effort", "thinking_steps"]
