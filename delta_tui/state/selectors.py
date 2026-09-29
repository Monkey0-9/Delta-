"""Read-only selectors over the store (screens never touch backend directly)."""
from __future__ import annotations

from .store import TerminalStore


def header_model(s: TerminalStore) -> dict:
    return {
        "mode": s.mode.value,
        "workspace": s.workspace,
        "symbol": s.symbol,
        "data": "LIVE" if s.data_live else "CACHED",
        "model": s.model,
        "broker": s.broker,
        "kill": "ARMED" if s.kill_armed else "OFF",
    }


def status_model(s: TerminalStore) -> dict:
    return header_model(s) | {"updated_at": s.updated_at, "alerts": len(s.alerts)}
