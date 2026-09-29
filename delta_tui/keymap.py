"""Leader-key map: Ctrl+X then key. Ctrl+K alone is NEVER kill."""
from __future__ import annotations

LEADER = "ctrl+x"

BINDINGS: dict[str, str] = {
    "ctrl+x h": "home",
    "ctrl+x m": "market",
    "ctrl+x b": "book",
    "ctrl+x r": "research",
    "ctrl+x a": "alpha",
    "ctrl+x p": "portfolio",
    "ctrl+x k": "risk",       # risk cockpit; kill needs confirm below
    "ctrl+x e": "execution",
    "ctrl+x o": "orders",
    "ctrl+x s": "system",
    "ctrl+x n": "research_new",
    "ctrl+x t": "session_new",
    "ctrl+p": "palette",
    "escape": "back",
    "tab": "next_pane",
}

# Emergency sequence: leader, then K, then typed confirmation. Bypasses LLM.
KILL_SEQUENCE = ("ctrl+x", "k", "kill-confirm")
