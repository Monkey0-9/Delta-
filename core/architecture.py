"""Group 01 — Package dependency rules (tui->controllers->domain, never reverse).

Bounded contexts: data | alpha | world | portfolio | risk | execution | research.
One owner module per context. Public interfaces via __init__ exports only.
Serialization: frozen dataclass viewmodels. Events: typed (delta_tui/state/events.py).
"""
from __future__ import annotations

ALLOWED = {
    "delta_tui": {"config", "delta_tui"},
    "apps": {"apps", "config", "delta_tui"},
    "research": {"config", "research", "data"},
    "execution": {"config", "execution", "risk"},
    "risk": {"config", "risk"},
}

OWNERS = {
    "data": "data",
    "alpha": "research/alpha",
    "world": "world_model",
    "portfolio": "portfolio",
    "risk": "risk",
    "execution": "execution",
    "research": "research/ledger",
}


def check_import(importer: str, imported: str) -> bool:
    """True if allowed. TUI must never be imported by domain layers."""
    if imported.startswith("delta_tui") and not importer.startswith(("delta_tui", "apps")):
        return False
    return True
