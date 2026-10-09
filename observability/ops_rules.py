"""B9: canonical ops alert rules — the SRE wiring contract.

Every rule binds a REAL metric name (observability.telemetry → Prometheus
`delta_*`, or a wired safety/feed probe in scripts/sre_check.py) to a
threshold, severity, runbook action, and owner. Aspirational Sprint-5 names
(feed_latency_nanoseconds, llm_ttft_ms, …) are NOT rules until a producer
emits them — claiming otherwise would be fake monitoring.

BASELINE NOTE (2026-10-09, this box): firewall check measures p50 ~163µs /
p99 ~343µs (see artifacts/bench/bench.json), NOT the 7µs P0-plan target —
the plan target is recorded as a bench FAIL, and these thresholds guard
against REGRESSION from the measured baseline instead of asserting an
unmet target (which would page constantly and teach operators to ignore
the pager).
"""
from __future__ import annotations

from dataclasses import dataclass

from observability.alerts import AlertRule


@dataclass(frozen=True, slots=True)
class OpsRule:
    rule: AlertRule
    meaning: str
    action: str
    owner: str


OPS_RULES: tuple[OpsRule, ...] = (
    OpsRule(AlertRule("kill-switch-engaged", "kill_switch_state", "gt", 0, "critical"),
            "Trading halted: kill switch active.",
            "Do NOT unlock to 'fix' alerts. Diagnose cause, resolve, then "
            "token + RISK_OFFICER+ role unlock per runbook.",
            "risk-officer"),
    OpsRule(AlertRule("risk-latency-p99-hot", "risk_latency_ns_p99", "gt", 700000, "warning"),
            "Pre-trade firewall p99 past 700µs (~2x the measured baseline).",
            "Check host load/Turbo Boost state; if sustained, halt new "
            "strategies and file a perf ticket (see bench artifact).",
            "engineering"),
    OpsRule(AlertRule("risk-latency-p99-critical", "risk_latency_ns_p99", "gt", 1400000, "critical"),
            "Firewall p99 past 1.4ms (~4x baseline) — pre-trade safety is degraded.",
            "Engage kill switch (panic path needs no role), then diagnose.",
            "risk-officer"),
    OpsRule(AlertRule("reject-rate-high", "rejection_rate", "gt", 0.05, "warning"),
            "More than 5% of orders rejected (risk/fault).",
            "Inspect reject reasons in the audit ledger; check limits + feed freshness.",
            "quant"),
    OpsRule(AlertRule("fill-ratio-low", "fill_ratio", "lt", 0.5, "warning"),
            "Fills below 50% of submitted — venue or simulation drift.",
            "Compare paper vs broker reports; run the DR drill if state is suspect.",
            "operations"),
    OpsRule(AlertRule("sequence-gaps", "gaps_total", "gt", 0, "warning"),
            "Market-data sequence gaps observed.",
            "Treat data as suspect: PIT gates should already block decisions; "
            "verify feed health before promoting any signal.",
            "operations"),
    OpsRule(AlertRule("queue-depth-high", "queue_depth", "gt", 10000, "warning"),
            "Internal queue backing up — consumer slower than producer.",
            "Check exporter/export lag and TUI event loop; shed non-critical load.",
            "engineering"),
    OpsRule(AlertRule("drawdown-breach", "drawdown", "lt", -0.02, "critical"),
            "Day drawdown past the 2% halt line.",
            "Kill switch should already be engaged by the sentinel; confirm "
            "HALTED, then review positions.",
            "risk-officer"),
)

RULES = tuple(r.rule for r in OPS_RULES)

__all__ = ["OPS_RULES", "RULES", "OpsRule"]
