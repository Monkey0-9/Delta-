"""Central terminal state store — ONE state model for the whole workstation."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from config.mode import DeltaMode


@dataclass
class Provenance:
    source: str = "unknown"
    as_of: str = ""
    freshness_s: float = 0.0
    confidence: str = "n/a"


@dataclass
class TerminalStore:
    mode: DeltaMode = DeltaMode.PAPER
    workspace: str = "home"
    session_id: str = "default"
    symbol: str = "NVDA"
    data_live: bool = False
    data_health: str = "HEALTHY"
    market_live: bool = False
    risk_state: str = "SAFE"
    model: str = "delta"
    agent: str = "delta"
    broker: str = "paper"
    kill_armed: bool = True
    viewmodels: dict[str, Any] = field(default_factory=dict)
    alerts: list[str] = field(default_factory=list)
    conversation: list[dict[str, str]] = field(default_factory=list)
    browser_ref: str = ""
    hypothesis: str = "H-2026-0041"
    experiment: str = "EXP-9182"
    strategy: str = "momentum-v4"
    dataset: str = "US_EQ_PIT_2026_08"
    research_status: str = "OOS validation"
    updated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    @property
    def context_str(self) -> str:
        parts = []
        if self.symbol:
            parts.append(self.symbol)
        parts.append(f"Portfolio {self.session_id.upper()}")
        if self.hypothesis and self.workspace == "research":
            parts.append(self.hypothesis)
        return " · ".join(parts) if parts else "none"

    def set_screen(self, name: str) -> None:
        self.workspace = name
        self.touch()

    def set_session(self, session_id: str) -> None:
        self.session_id = (session_id or "default").strip() or "default"
        self.touch()

    def set_agent(self, agent: str) -> None:
        self.agent = (agent or "delta").strip() or "delta"
        self.touch()

    def set_model(self, model: str) -> None:
        self.model = (model or "delta").strip() or "delta"
        self.touch()

    def append_turn(self, role: str, text: str) -> None:
        self.conversation.append({"role": role, "text": text})
        # keep transcript bounded; session file holds full history
        if len(self.conversation) > 200:
            del self.conversation[: len(self.conversation) - 200]
        self.touch()

    def set_mode(self, mode: DeltaMode) -> None:
        self.mode = mode
        self.touch()

    def publish(self, screen: str, vm: Any) -> None:
        self.viewmodels[screen] = vm
        self.touch()

    def touch(self) -> None:
        self.updated_at = datetime.now(timezone.utc).isoformat()


_store: TerminalStore | None = None


def get_store() -> TerminalStore:
    global _store
    if _store is None:
        _store = TerminalStore()
    return _store


def reset_store(mode: DeltaMode = DeltaMode.PAPER) -> TerminalStore:
    global _store
    _store = TerminalStore(mode=mode)
    return _store
