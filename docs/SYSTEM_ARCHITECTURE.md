# SYSTEM ARCHITECTURE — DELTA OS v1.0 (2026-10-07)

Status: DESIGNED / IMPLEMENTED (paper/sim) / TESTED / PAPER — SHADOW+PROD gated.

Pipeline (frozen order):
USER → DELTA TUI (COMMAND/AI/DATA) → RUNTIME (Research|Decision|Execution)
→ OMS → PAPER/SHADOW/BROKER → RECONCILE → OUTCOME+ATTRIBUTION → MEMORY/REGISTRY.

Invariants:
1. Truth over polish — every number carries SOURCE/AS-OF/FRESHNESS/CONFIDENCE or UNAVAILABLE.
2. Fail-closed risk — firewall vetoes pre-network; model recommends, firewall vetoes.
3. PIT integrity — t_event ≤ t_pub ≤ t_avail ≤ t_dec ≤ t_exec, enforced in code.
4. Idempotency — every order carries client_order_id + idempotency_key.
5. Kill bypasses LLM — Ctrl+X K → /kill CONFIRM → governor.

Contexts: data | alpha | world | portfolio | risk | execution | research.
Each context owns one package; tui→controllers→domain, never reverse.
Events: storage/event_store (append/replay). Audit: SHA-256 chain.
Modes: LIVE|PAPER|SIMULATION|RESEARCH|DEMO (+SHADOW as PAPER-family alias pending true split).
LIVE = ERR_LIVE_PROHIBITED until R10.
