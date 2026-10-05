# ADR 0002 — Bounded contexts and domain ownership (Group 01)

- Status: accepted / Date: 2026-10-02 / Version: 1.0
- Contexts: `data | alpha | world | portfolio | risk | execution | research`.
- Owners: data->`data/`, alpha->`research/alpha*`, world->`world_model/`,
  portfolio->`portfolio/`, risk->`risk/`, execution->`execution/`,
  research->`research/ledger/`.
- Rule: `delta_tui -> controllers -> domain`, never reverse
  (enforced by `core/architecture.py::check_import` + `scripts/arch_lint.py`).
- Public interfaces: per-context `__init__` exports only; viewmodels are
  frozen dataclasses (`delta_tui/viewmodels/models.py`); events are typed
  (`delta_tui/state/events.py`).
