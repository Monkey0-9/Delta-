# Plans — index (newest first)

Authoritative build plans live here. `DELTA_VNEXT_PLAN.md` (repo root) remains the
frozen program order; these files are its full working detail. No duplicates:
the TUI deep-dive is the expanded UI-1→UI-5 companion of the master plan.

* `2026-10-07-model-switch-fix.md` — THE v2.2 record. User-reported switch/MCP/think/key
  failures reproduced live, root-caused, fixed (routing pins, persist, agent
  default, bleed), temp-vault key E2E. `test_model_switch` 9/9.
* `2026-10-07-guide-proof-sweep.md` — THE v2.1 record. Every guide claim probed live;
  6 shame events killed (token-less unlock, fake $1M P&L, 4 unknown screens,
  web-availability lie, fictional hotkeys, Java numbers) + runtime verdict
  (no C#/JS on measurement). 968 + cargo 25/25. Start here for demo readiness.
* `2026-10-07-v20-complete-update.md` — THE v2.0 record. Per-stage completion table with
  file:line evidence, R-gate table, user-facing changes, remaining wall-clock work.
  Counts 961 + cargo 25/25. Start here for current truth.
* `2026-10-05-delta-complete-os.md` — THE master. A→Z gap matrix with honest
  Implemented/Partial/Missing labels + file:line evidence, missing control layers
  (unified state/event-sourcing, drift/disagreement/uncertainty, hierarchical kill,
  offline/fallback/rollback, evidence graph), frozen build order
  (Foundation → Quant → Research→Decision → Validation → Reality), P0–P3 tiers,
  per-stage verification, risks/reversal. Start here.
* `2026-10-07-audit-closure.md` — Audit verdict. Full A-Z+ re-verified with code:line
  pointers, 3 gaps closed (DATA screen, bridge probe, commands.toml), counts
  961 + cargo 25/25, outcome vs expectation + what still needs wall-clock work.
* `2026-10-05-delta-tui-deepdive.md` — Companion. OpenCode interaction model +
  Bloomberg density + quant workflow: HOME 4-pane, full command registry,
  `/model /agent /mcp`, `@` refs, `!` allowlist, palette, evidence cards,
  consensus matrix, Why-drilldown, `/doctor /status`, sessions, config-driven
  theme/layout/keys, UI-1→UI-5 order. Read after the master.

Conventions: one date-prefixed file per plan, never edit in place — add a new
dated file. Labels stay honest; wall-clock gates (14-day soak, hardware benches,
R10 sign-off) are evidence, not checkboxes.
