"""Responsive helper:呼ば width -> visible panes."""
from __future__ import annotations

from .themes import layout_for


def panes(width: int) -> dict:
    mode = layout_for(width)
    return {
        "mode": mode,
        "nav": mode in ("full", "normal"),
        "context": mode in ("full", "normal"),
        "collapsed_context": mode == "collapsed",
    }
