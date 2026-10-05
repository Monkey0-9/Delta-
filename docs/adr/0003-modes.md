# ADR 0003 — Explicit modes LIVE|PAPER|SIMULATION|RESEARCH|DEMO (Group 03/04)

- Status: accepted / Date: 2026-10-02 / Version: 1.0
- `config/mode.py::DeltaMode` is the single source of truth.
- `portfolio-review` prints actual state; synthetic paths require
  `--simulation`/`--mode` and carry `SOURCE/synthetic-DEMO` badges.
- LIVE is fail-closed: requires `DELTA_LIVE=ARMED` + `LiveAuthorization` +
  health + kill-board + fresh-data (see `core/vault.py`, `execution/live_engine.py`).
- Every number carries SOURCE / AS-OF / FRESHNESS / CONFIDENCE.
