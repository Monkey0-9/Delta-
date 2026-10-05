"""Group 09 — Command UX: fuzzy rank, unknown guidance, NL parity, kill bypass.

Slash + NL converge on action model (registry.lookup). Kill always bypasses LLM.
"""
from __future__ import annotations

import difflib

from .registry import REGISTRY, lookup


def fuzzy_rank(query: str, limit: int = 5) -> list[str]:
    names = list(REGISTRY)
    q = (query or "").lower().strip("/ ")
    scored = sorted(names, key=lambda n: (
        0 if n == q else 1 if n.startswith(q) else 2,
        -difflib.SequenceMatcher(None, q, n).ratio(),
    ))
    return scored[:limit]


def unknown_guidance(raw: str) -> str:
    sug = ", ".join(fuzzy_rank(raw, 3))
    return f"Unknown command '{raw}'. Did you mean: {sug}? Try /help."


def nl_to_action(text: str) -> str:
    t = (text or "").lower()
    if "kill" in t:
        return "kill"
    if "book" in t or "depth" in t:
        return "book"
    if "risk" in t or "stress" in t:
        return "risk"
    if "alpha" in t:
        return "alpha"
    if "portfolio" in t or "position" in t:
        return "portfolio"
    if "scenario" in t:
        return "simulate"
    return "help"


def dispatch(raw: str, *, confirmed: bool = False) -> str:
    """Never empty; kill bypasses LLM and requires CONFIRM (see permissions)."""
    from delta_tui.security.permissions import check
    name = (raw or "").strip().split()[0] if raw and raw.startswith("/") else nl_to_action(raw)
    name = name.strip("/ ")
    act = lookup(name)
    if act is None:
        return unknown_guidance(raw)
    perm = check(name, confirmed=confirmed)
    if perm.needs_confirm:
        return f"CONFIRM required for /{name}: {perm.reason}"
    if act.run:
        return act.run({"confirmed": confirmed})
    return f"SCREEN:{act.screen}"
