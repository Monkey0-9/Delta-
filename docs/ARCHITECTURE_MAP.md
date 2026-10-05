# DELTA Interaction-Architecture Map (Phase 0A, 2026-10-02)

```
TUI (tui/src + delta_tui/) ── JSON-RPC/IPC ── Python Delta Runtime
        │                                               │
        │ commands (registry-driven)                    ├── command handling (same registry)
        │ @ context (resolved pre-model)                ├── agent orchestrator -> model + tools/MCP
        │ DESK/Markets/Portfolio/Risk/...               ├── data (provider registry + PIT + security master)
        │                                               ├── models (registry, no substring inference)
        │                                               ├── agents (deterministic risk-governor)
        │                                               ├── risk (firewall) -> execution (OMS/router)
        │                                               │       ├── Python Paper / Live Adapters
        │                                               │       └── Java Disruptor Engine (ADR-0007: Paper/Sim)
        │                                               ├── broker registry (paper/live adapters)
        │                                               └── reconciliation -> audit (SHA-256)
```

## Duplication retired
- `data/security_master.py` (shadow file) removed; canonical:
  `data/security_master/` + `global_resolver.py` (multi-venue ambiguity).
- `broker/registry.py` (adapter handles) kept; connection/account/capability
  model added in `execution/broker_registry.py` (separate concerns).
- `delta_tui/commands/ux.py` + `aliases.py` kept; full surface in
  `terminal.py`, auto-loaded by `delta_tui/commands/__init__.py`.
- Mode authority: `config/mode.py` + `execution/routing_policy.py::MODES`
  (capability matrix, not UI strings).

## Demo-state rule: NO_DEMO_STATE_IN_PRODUCTION_RUNTIME
Removed: `184.20` fallback, `100`-share default, hardcoded RSI/MACD/Sharpe/
ReasonForge texts, `8 MCP SERVERS...CERTIFIED`, `$1,000,000` equity fallback.
Guard: `test_no_demo_state_in_production_runtime` (Python) +
`test_order_ticket_blocked_without_quote` (Rust).
Research/SIM fixtures must carry SIM/SYNTHETIC/FIXTURE/TEST labels.

## Interface decision (ADR-0006): CLI + TUI only for humans
No web UI exists and none is planned (inventory 2026-10-02: no HTML, no
flask/fastapi/streamlit, no Grafana configs). `observability/dashboard.py`
is JSON ops telemetry, not a UI — retained. Nothing to retire; nothing
was moved to `archive/` for this decision.
