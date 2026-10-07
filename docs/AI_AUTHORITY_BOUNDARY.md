# FINANCE AI AUTHORITY BOUNDARY (Stage-2 K) — v1.0 2026-10-07

Finance AI DOES: financial reasoning, research synthesis, tool selection,
hypothesis generation, experiment planning, news interpretation, portfolio/risk
explanation, report generation — always with evidence + provenance.

Finance AI NEVER: produces numerical alpha directly, places/cancels/modifies
orders, bypasses risk firewall, touches broker credentials, overrides kill-switch,
or presents synthetic numbers as live state.

Enforcement: deterministic layers own numbers/orders/risk. Any LLM-emitted
order intent (buy/sell/cancel/flatten + qty/symbol) is refused with
`AUTHORITY_REFUSED` and audited. Tests: test_stage2_quantbrain.py.
