# 2026-10-07 — Model switching / MCP / think / key fix (v2.2)

> User report: "model switching is not happening, for MCPs also, think for
> all; there should be API-key add for models." Every item reproduced live
> before fixing. Evidence: `tests/test_model_switch.py` 9/9.

## Root causes (all confirmed by live probe, not guessed)

1. **Switch was a label-swap**: `_c_model switch` set `Terminal.model_name`
   but never touched `ModelGateway.active` — and `_ask` routes on the
   `commentary` role, ignoring the label. Catalogue names had no gateway rails.
2. **TUI poisoned its own display**: `_cmd_model` split backend text on `"->"`
   and stored the whole trailing sentence as `store.model`.
3. **`/effort` / `/thinking` evaporated** on both rails (printed ✓, stored nothing,
   applied nothing; TUI rendered an unrelated screen + stale backend echo).
4. **Default agent `quant-researcher` ∉ AGENTS** — `/agent quant-researcher` answered
   "unknown agent" for the out-of-box default.
5. **Stale backend echo bled across screens** (`_last_live` never cleared).
6. Key-add worked only via an undiscoverable vault flow (no regression, but
   unusable in practice).

## Fixes

- `delta_os/llm_gateway.py`: catalogue-wired PROVIDERS (11 rails) +
  `CATALOGUE_TO_PROVIDER` + `use_catalogue()` (pins commentary role) +
  `EFFORT_PROFILES` + `set_effort()` applied to cloud/local `max_tokens`+timeout.
- `delta_os/repl.py`: `effort`/`thinking` fields + session persist; switch pins
  routing + persists; effort/thinking apply + persist; thinking drives tool-evidence
  verbosity (OFF/SUMMARY/ACTIVITY); `/key` locked-vault reply gives exact 3 steps.
- `delta_tui/app.py`: `effort/thinking/key` passthrough branches; robust model-token
  parse; effort/thinking chip sync; `_last_live` cleared per dispatch; agent legacy
  alias (`quant-researcher`→`research-agent`).
- `delta_tui/state/store.py`: default agent `research-agent` + effort/thinking
  fields; session.json round-trips all four.
- `tests/unit/test_opencode_design.py`: frontpart assertions follow the corrected default.
- Key E2E proven with temp vault: unlock → `/key` → READY → switch pins
  `commentary` → `_key()` returns the stored secret; keyless cloud refused;
  rail-less template refused even when keyed.

## Counts

`test_model_switch` 9/9; blast radius 100/100; targeted re-run 36/36.
MCP note: `/mcp` + `/tools` verified working on both rails (declared-capability
tables, UNPROBED-honest); no code change needed there.
