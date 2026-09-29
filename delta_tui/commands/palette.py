"""Command palette entries (Ctrl+P). Textual-optional: pure data + filter."""
from __future__ import annotations

from .registry import REGISTRY


def entries(query: str = "") -> list[dict]:
    q = (query or "").lower().strip("/")
    out = []
    for a in REGISTRY.values():
        if not q or q in a.name or q in a.description.lower() or q in a.category.lower():
            out.append({
                "name": "/" + a.name,
                "description": a.description,
                "screen": a.screen,
                "category": getattr(a, "category", "Primary"),
                "risky": a.risky,
            })
    # Sort Primary first, then System/AI, then alphabetically by name
    return sorted(out, key=lambda e: (0 if e["category"] == "Primary" else 1, e["name"]))
