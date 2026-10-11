# ADR 0008 — Canonical owners + Rust terminal (P1 reconciliation)

- Version: 1.0 / Date: 2026-10-11 / Status: accepted
- Context: overlapping subsystems (`tui/` vs `delta_tui/`, `agent/` vs
  `agents/`, `ai/` vs `models/` vs `finance_model/`, `core/oms/` vs
  `execution/oms/`, `data/pit/` vs `data/tick_pit/`, dual risk/audit paths)
  plus a direct frontend conflict (ADR-0001 names `delta_tui/`/Textual the
  ONE frontend; README/launcher/AGENTS.md name Rust Ratatui). No
  undocumented production bypass can survive this ambiguity.
- Decision:
  1. The interactive terminal is Rust Ratatui/Crossterm (`tui/`). ADR-0001's
     "ONE frontend `delta_tui/` (Textual+Rich)" is SUPERSEDED. `delta_tui/`
     is retained only as the headless/Python fallback behind the launcher
     (`apps/cli/delta.py`: native binary first, `DeltaApp` fallback); it
     must never present itself as the primary terminal, and new interactive
     work lands in `tui/` only.
  2. Canonical owners (all other implementations are adapter, experiment,
     or retired legacy — labeled at the module, never silent):
     - Command API: `core/command_bus.py` (typed contract); REPL table,
       typer CLI, `config/commands.toml` are views that must converge.
     - Market data + PIT: `data/` access contract; `data/tick_pit/pit_store.py`
       is the persistent tick store; `data/pit/` (query/leakage/manifests)
       consumes it. Provider adapters live under `data/providers/`.
     - Research: `research/` pipeline with manifests + dataset hashes;
       promotion gates enforced in promotion code (P2).
     - Risk + authorization: `risk/firewall/` + `risk/kill_switch/` +
       `security/authorization.py` enforced via `core/oms/gateway.py`
       (require_role=True default, P0-4). Analytic-only copies are not
       enforcement paths.
     - OMS + execution: `core/oms/` (gateway + journal) is canonical.
       `execution/oms/state_machine.py` is RETIRED legacy (wave-test-only;
       must not be imported by production paths).
     - AI + agents: single inference/tool gateway (P3); until merged,
       `agent/` (runtime/tools/policies) is canonical over `agents/`
       (fleet/contracts), and `models/` registry fronts providers.
     - Portfolio state: one versioned state model (P1 durability work).
     - Audit: one durable hash-chained store (`core/oms/journal.py` +
       persisted compliance chain); in-memory-only chains are not evidence.
     - Operations: `observability/ops_rules.py` + SRE runbook + verified
       paging (P4); placeholder contacts never ship as configured.
  3. `DELTA_VNEXT_PLAN.md` frontend items (§1, P0 line 134) are annotated
     superseded-by-0008, not rewritten: history stays readable.
- Consequences: any new import of a retired module by a production path is
  a review-blocking violation; `scripts/arch_lint.py` should enforce the
  retired list (P1 follow-up).
