"""Command palette entries (Ctrl+P). Textual-optional: pure data + filter."""
from __future__ import annotations

from .registry import REGISTRY


def entries(query: str = "") -> list[dict]:
    q = (query or "").lower().strip("/")
    out = []
    for a in REGISTRY.values():
        if not q or q in a.name or q in a.description.lower():
            out.append({"name": "/" + a.name, "description": a.description,
                        "screen": a.screen, "risky": a.risky})
    return sorted(out, key=lambda e: e["name"])
