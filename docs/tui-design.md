# TUI design system (Group 06) — v1.0 2026-10-01, active

Typography/spacing/panel/table via Rich renderables. Status chips:
DATA/MODEL/BROKER/KILL/latency. Alerts: risk breach, stale data.
Numeric: `Number` viewmodel with fmt. Positive/negative theme-driven.
Provenance badges: mode + source/as-of on every screen.
A11y: high-contrast theme, no-color mode, unicode fallback (cp1252-safe),
plain-text render path per screen (`delta_tui/a11y.py`).
