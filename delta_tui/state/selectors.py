"""Read-only selectors over the store (screens never touch backend directly)."""
from __future__ import annotations

from .store import TerminalStore


def header_model(s: TerminalStore) -> dict:
    from datetime import datetime, timezone

    # A3: HEALTHY only when a feed reports live. A HEALTHY flag with
    # data_live=False (e.g. store default) derives to DEGRADED — never show
    # a healthy dot on a dark feed. Explicit UNAVAILABLE is preserved.
    _health = (s.data_health or "").upper()
    if bool(s.data_live) and _health == "HEALTHY":
        _data = "HEALTHY"
    elif _health in ("DEGRADED", "UNAVAILABLE"):
        _data = _health
    else:
        _data = "DEGRADED"
    return {
        "mode": s.mode.value,
        "workspace": s.workspace,
        "symbol": s.symbol,
        "market": "LIVE" if s.market_live else "CLOSED",
        "data": _data,
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
        "context": s.context_str,
        "mode": s.mode.value,
        "risk": s.risk_state or "SAFE",
    }


def status_model(s: TerminalStore) -> dict:
    return header_model(s) | {"updated_at": s.updated_at, "alerts": len(s.alerts)}
