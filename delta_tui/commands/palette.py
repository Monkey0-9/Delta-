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
    # Sort Primary first, then System/AI, then preserve priority
    order = [
        "/research", "/market", "/portfolio", "/risk", "/simulate",
        "/backtest", "/trade", "/automation", "/finance-chat", "/finance-agent",
        "/kill-switch", "/model", "/agent", "/mcp", "/auth", "/session", "/config", "/open"
    ]
    def sort_key(e):
        name = e["name"]
        idx = order.index(name) if name in order else 99
        return (0 if e["category"] == "Primary" else 1, idx, e["name"])

    return sorted(out, key=sort_key)


def format_palette_box(query: str = "") -> str:
    """Renders the exact Section 8 contextual command palette box."""
    rows = entries(query)
    primary = [r for r in rows if r.get("category") == "Primary"]
    system = [r for r in rows if r.get("category") != "Primary"]

    width = 45
    lines = [
        "╭" + "─" * (width + 2) + "╮",
        f"│ {'Search commands...':<{width}} │",
        f"│ {'':<{width}} │",
    ]

    for r in primary[:11]:
        line_content = f"{r['name']:<15} {r['description']}"
        lines.append(f"│ {line_content[:width]:<{width}} │")

    if not query and system:
        lines.append(f"│ {'':<{width}} │")
        lines.append(f"│ {'System/AI:':<{width}} │")
        for r in system[:7]:
            line_content = f"{r['name']:<15} {r['description']}"
            lines.append(f"│ {line_content[:width]:<{width}} │")

    lines.append(f"│ {'':<{width}} │")
    lines.append(f"│ {'↑↓ Navigate   Enter Select   Esc Close':<{width}} │")
    lines.append("╰" + "─" * (width + 2) + "╯")
    return "\n".join(lines)
