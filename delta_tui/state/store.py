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
    model: str = "rules"
    broker: str = "paper"
    kill_armed: bool = True
    viewmodels: dict[str, Any] = field(default_factory=dict)
    alerts: list[str] = field(default_factory=list)
    updated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def set_screen(self, name: str) -> None:
        self.workspace = name
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
