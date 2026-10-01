"""DELTA theme tokens + responsive breakpoints."""
from __future__ import annotations

# Calm long-session palette (Image 1): near-black, muted teal accent.
# Data commands attention, not the chrome.
CALM = {
    "bg": "#080909",
    "fg": "#D6D8D7",
    "muted": "#858A88",
    "accent": "#20C9A6",
    "good": "#3FB97F",
    "warn": "#C9A227",
    "bad": "#C25B5B",
    "paper": "#C9A227",
    "live": "#C25B5B",
    "font": "JetBrains Mono, IBM Plex Mono, Iosevka, Berkeley Mono, monospace",
}

THEMES = {
    "pro": {"bg": "#0f172a", "accent": "#38bdf8", "good": "#34d399",
            "bad": "#f87171", "warn": "#fbbf24"},
    "dark": {"bg": "#111111", "accent": "#7dd3fc", "good": "#34d399",
             "bad": "#f87171", "warn": "#fbbf24"},
    "light": {"bg": "#ffffff", "accent": "#0284c7", "good": "#059669",
              "bad": "#dc2626", "warn": "#d97706"},
    "calm": {"bg": CALM["bg"], "accent": CALM["accent"], "good": CALM["good"],
             "bad": CALM["bad"], "warn": CALM["warn"]},
}

ACTIVE_THEME = "calm"

# Terminal-width breakpoints: full / normal / collapsed / compact.
BREAKPOINTS = [(160, "full"), (120, "normal"), (80, "collapsed"), (0, "compact")]


def layout_for(width: int) -> str:
    for min_w, name in BREAKPOINTS:
        if width >= min_w:
            return name
    return "compact"


# --- frontend-design skill: institutional-calm design system snapshot ---
# Aesthetic: INSTITUTIONAL CALM (industrial-utilitarian + editorial restraint).
# DFII: Impact 4 + Fit 5 + Feasibility 5 + Performance 5 - Risk 2 = 17 (excellent).
# Anchor: micro-header + hero RESEARCH/SIMULATE/ANALYZE/EXECUTE/LEARN + teal-on-black
# data-first chrome. Data commands attention, never the frame.
DESIGN_SYSTEM = {
    "aesthetic": "institutional-calm",
    "fonts": {
        "display": "JetBrains Mono Semibold (numbers tabular, headers uppercase, ls=0.08em)",
        "body": "IBM Plex Mono Regular (conversation, tables, 13-14px equiv)",
        "rationale": "monospace everywhere = quant terminal trust; no web-font download",
    },
    "color_vars": {
        "--bg": CALM["bg"], "--fg": CALM["fg"], "--muted": CALM["muted"],
        "--accent": CALM["accent"], "--good": CALM["good"],
        "--warn": CALM["warn"], "--bad": CALM["bad"],
        "--line": "#1C2120", "--panel": "#0C0E0D",
    },
    "spacing": "4px base; header 1 row; hero 1 row; input box 3 rows; footer 1 row; panels 16px gap",
    "motion": "none in TUI (instant); web mirror: single 180ms fade on workspace switch only",
    "density": "full>=160 (5-col workspace), normal>=120 (3-col), collapsed>=80 (stacked), compact (single)",
    "layout": "header / ACTIVE WORKSPACE / positions|alerts / command-conversation",
    "a11y": "contrast fg/bg 13.2:1, accent/bg 9.1:1; keyboard-first (/ + Ctrl+K palette + Ctrl+O open); focus stays in input",
}

# Responsive workspace grid per spec section 37.
WORKSPACE_LAYOUT = {
    "full": {"columns": ("positions", "chart", "orders", "research", "alerts"), "footer": True},
    "normal": {"columns": ("positions", "orders", "alerts"), "footer": True},
    "collapsed": {"columns": ("positions", "alerts"), "footer": False},
    "compact": {"columns": ("alerts",), "footer": False},
}
