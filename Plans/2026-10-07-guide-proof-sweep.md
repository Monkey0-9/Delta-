# 2026-10-07 — Guide-proof sweep: every USER_GUIDE claim tested live (v2.1)

> Method: probed all 70+ guide commands through BOTH rails (TUI registry +
> REPL `handle`), read every output, fixed every dead end. Evidence:
> `tests/test_guide_proof.py` 7/7 (fails the build on any future dead end).

## Shame events found and killed

1. **CRITICAL — unlock without token** (`delta_os/repl.py`): `/unlock <anything>`
   left HALTED with no authentication while the guide promised authenticated
   unlock. Now requires `DELTA_UNLOCK_TOKEN` (`/unlock <token> [actor]
   [reason...]`); denials audited, engine stays HALTED. Proven: wrong token held,
   right token resumed. `tests/test_delta_os.py` updated to the secure contract.
2. **Fake +$1M day-P&L** (status bar): fresh REPL showed `+1,000,000.00` day P&L
   (equity-minus-zero). Now `n/a (no day-start equity)` until initialized.
3. **Four guide screens printed `unknown`** (`/lab /exec /recon /audit`): built
   real `ReconScreen` + `AuditScreen` (`delta_tui/screens/assurance.py`,
   engine-backed, UNAVAILABLE-honest); registered 12 missing TUI commands;
   remapped 15 dead screen targets to real screens; `test_every_registry_screen_exists`
   guards all of it.
4. **False `DELTA Web` availability claim** in `delta_tui/app.py` dispatch
   (ADR-0006: no web UI exists or planned): replaced with terminal-native
   `/export` hint. `/open` was already honest (NOT IMPLEMENTED + ref stored).
5. **Fictional hotkeys** (F1–F9, `:` , Ctrl+C-kill, Ctrl+Q): replaced with the
   real `keymap.py` map (Ctrl+X leader, Ctrl+P/K palette, Ctrl+X K + `/kill CONFIRM`).
6. **Java numbers**: `22.1M ops/s p99 100ns` replaced with lane-honest figures
   (ring 14.2M certified; loopback measured 17,711/s p50 48µs this box).

## Runtime verdict (measured, not believed)

Java 4/4 suites pass; stays as PAPER/SIM execution-plane transport — NOT a
replacement for the durable Python OMS journal (5,200 fsync'd ops/s).
**No C#, no JS**: fourth runtime + extra IPC hops would add latency, not remove
it; JDK25 ring already exceeds transport need 1000x. Record:
`docs/PERF_RUNTIME_VERDICT.md`.

## Counts

pytest **968 passed** (853 + 115 institutional) + cargo tui 25/25 +
15-command live-dispatch smoke with zero `unknown`. Doctor GO-PAPER 6/11.
LIVE stays `ERR_LIVE_PROHIBITED`.
