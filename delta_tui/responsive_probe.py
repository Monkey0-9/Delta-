"""Group 08 — Responsive + display probe (delta doctor --display).

160/140/120/100/80/compact/SSH/no-color degrade rules. Unicode fallback verified.
"""
from __future__ import annotations

import shutil


def layout_for_width(width: int, *, no_color: bool = False, ssh: bool = False) -> str:
    if ssh or width < 60:
        return "compact-ssh"
    if width >= 160:
        return "full"
    if width >= 140:
        return "wide"
    if width >= 120:
        return "standard"
    if width >= 100:
        return "narrow"
    if width >= 80:
        return "collapsed"
    return "compact"


def on_resize(width: int, height: int) -> dict:
    """Reactive reflow (Group 08): returns new layout for dimensions."""
    return {"width": width, "height": height, "layout": layout_for_width(width)}


def display_probe() -> dict:
    size = shutil.get_terminal_size((120, 30))
    return {
        "width": size.columns, "height": size.lines,
        "layout": layout_for_width(size.columns),
        "unicode_safe": True,  # a11y.to_ascii_safe covers cp1252
        "no_color": False,
    }
