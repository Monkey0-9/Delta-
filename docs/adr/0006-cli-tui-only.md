# ADR 0006 — CLI + TUI are the only human interfaces (2026-10-02)

- Status: accepted / Version: 1.0
- Human surfaces: Rust Ratatui TUI (`tui/`, primary workstation) + Python
  Textual TUI (`delta_tui/`, fallback rail) + CLI (`apps/cli/`,
  `delta /quote NVDA`, `delta --api`, `delta --json`).
- Machine surfaces: headless / HTTP / WS on `apps/api_contracts.py` —
  same runtime services, never a human workflow.
- No browser/web dashboard for humans. Inventory 2026-10-02 found none
  (no HTML, no flask/fastapi/streamlit, no Grafana configs);
  `observability/dashboard.py` is a JSON ops-telemetry snapshot, not a UI.
- Rationale: terminal is the workstation (keyboard density, deterministic
  local kill path, single `DeltaRuntimeContext` — no second state layer).
- Gate: `tests/test_interface_parity.py` (CLI map <-> TUI registry <->
  runtime services must agree).
