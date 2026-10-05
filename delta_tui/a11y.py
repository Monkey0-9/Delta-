"""Group 06/08 — Accessibility: high-contrast, no-color, screen-reader, unicode fallback.

Windows cp1252-safe: strip/replace non-encodable glyphs when unicode unavailable.
Every screen offers plain-text render path for screen readers.
"""
from __future__ import annotations


def to_ascii_safe(text: str) -> str:
    return (text or "").encode("cp1252", errors="replace").decode("cp1252")


def strip_style(text: str, *, no_color: bool) -> str:
    if not no_color:
        return text or ""
    import re
    return re.sub(r"\[/?[a-zA-Z0-9 _#;:]+\]", "", text or "")


def plain_text(screen: str, vm: object) -> str:
    """Screen-reader-friendly output: never empty, never markup-sniffed."""
    body = getattr(vm, "summary", None) or str(vm)
    lines = [f"{screen} screen.", str(body)]
    return "\n".join(lines)


HIGH_CONTRAST_THEME = {"bg": "black", "fg": "white", "accent": "yellow"}
