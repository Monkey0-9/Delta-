"""DELTA theme tokens + responsive breakpoints."""
from __future__ import annotations

THEMES = {
    "pro": {"bg": "#0f172a", "accent": "#38bdf8", "good": "#34d399",
            "bad": "#f87171", "warn": "#fbbf24"},
    "dark": {"bg": "#111111", "accent": "#7dd3fc", "good": "#34d399",
             "bad": "#f87171", "warn": "#fbbf24"},
    "light": {"bg": "#ffffff", "accent": "#0284c7", "good": "#059669",
              "bad": "#dc2626", "warn": "#d97706"},
}

# Terminal-width breakpoints: full / normal / collapsed / compact.
BREAKPOINTS = [(160, "full"), (120, "normal"), (80, "collapsed"), (0, "compact")]


def layout_for(width: int) -> str:
    for min_w, name in BREAKPOINTS:
        if width >= min_w:
            return name
    return "compact"
