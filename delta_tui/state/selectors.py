"""Read-only selectors over the store (screens never touch backend directly)."""
from __future__ import annotations

from .store import TerminalStore


def header_model(s: TerminalStore) -> dict:
    from datetime import datetime, timezone

    return {
        "mode": s.mode.value,
        "workspace": s.workspace,
        "symbol": s.symbol,
        "market": "LIVE" if s.market_live else "CLOSED",
        "data": s.data_health or ("LIVE" if s.data_live else "CACHED"),
        "risk": s.risk_state or "SAFE",
        "model": s.model,
        "agent": s.agent,
        "session": s.session_id,
        "broker": s.broker,
        "kill": "ARMED" if s.kill_armed else "OFF",
        "clock_utc": datetime.now(timezone.utc).strftime("%H:%M:%S UTC"),
    }


def footer_model(s: TerminalStore) -> dict:
    return {
        "model": s.model,
        "agent": s.agent,
        "session": s.session_id,
        "mode": s.mode.value,
        "risk": s.risk_state or "SAFE",
    }


def status_model(s: TerminalStore) -> dict:
    return header_model(s) | {"updated_at": s.updated_at, "alerts": len(s.alerts)}
