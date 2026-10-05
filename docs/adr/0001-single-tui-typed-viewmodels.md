# ADR 0001 — Single TUI + typed viewmodels (vNext freeze)

- Version: 1.0 / Date: 2026-10-01 / Status: accepted
- Context: duplicate launch paths + string-sniffing widgets caused demo/prod confusion.
- Decision: ONE frontend `delta_tui/` (Textual+Rich). `apps/cli/delta.py -> delta_tui.app`.
  Backend returns frozen dataclass viewmodels. Widgets never sniff strings.
  Modes explicit: LIVE|PAPER|SIMULATION|RESEARCH|DEMO.
- Consequences: legacy CLI quarantined; kill bypasses LLM; every number carries SOURCE/AS-OF/FRESHNESS/CONFIDENCE.
