"""Slash + natural-language parser onto the single action model."""
from __future__ import annotations

import re

from .registry import lookup

_SYM = re.compile(r"\b([A-Z]{1,5})\b")


def parse(text: str) -> dict:
    t = (text or "").strip()
    if t.startswith("/"):
        parts = t[1:].split()
        action = lookup(parts[0]) if parts else None
        return {"kind": "slash", "action": action,
                "args": parts[1:], "raw": t}
    low = t.lower()
    for name in ("book", "market", "portfolio", "risk", "research",
                 "alpha", "execution", "orders", "system", "scenario"):
        if low.startswith("/" + name) or low.startswith(name):
            m = _SYM.search(t.upper())
            return {"kind": "nl", "action": lookup(name),
                    "args": [m.group(1)] if m else [], "raw": t}
    if "kill" in low:
        return {"kind": "nl", "action": lookup("kill"), "args": [], "raw": t}
    m = _SYM.search(t.upper())
    if m and len(t.split()) <= 4:
        return {"kind": "nl", "action": lookup("analyze"),
                "args": [m.group(1)], "raw": t}
    return {"kind": "chat", "action": None, "args": [], "raw": t}
