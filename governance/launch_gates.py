"""Shared launch gates (both strategy + LLM) + unified launch verdict.

Shared: sign-off w/ success criteria, docs/specs/assumptions/limits,
monitoring live pre-launch, kill-switch tested (not documented), on-call plan.
Critical gates: strategy overfit-block + LLM observability-block are vetoes.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Verdict:
    check: str
    ok: bool
    evidence: str
    detail: dict = field(default_factory=dict)


def check_signoff(signs: dict[str, bool], criteria_defined: bool) -> Verdict:
    required = {"quant", "engineering", "risk", "infosec", "operations"}
    ok = required.issubset({k for k, v in signs.items() if v}) and criteria_defined
    missing = sorted(required - {k for k, v in signs.items() if v})
    return Verdict("S1-signoff", ok, f"missing={missing} criteria={criteria_defined}",
                   {"missing": missing})


def check_docs(specs: bool, assumptions: bool, limits: bool) -> Verdict:
    ok = specs and assumptions and limits
    return Verdict("S2-docs", ok,
                   f"specs={specs} assumptions={assumptions} limits={limits}", {})


def check_monitoring(live_before_launch: bool, alerts: bool, dashboards: bool) -> Verdict:
    ok = live_before_launch and alerts and dashboards
    return Verdict("S3-monitoring", ok,
                   f"live_pre_launch={live_before_launch} alerts={alerts} dash={dashboards}",
                   {})


def check_killswitch(drilled: bool, last_drill_days_ago: float) -> Verdict:
    ok = drilled and last_drill_days_ago <= 30
    return Verdict("S4-killswitch", ok,
                   f"drilled={drilled} days_ago={last_drill_days_ago} (tested, not documented)",
                   {})


def check_oncall(plan_defined: bool, rota_set: bool, runbooks: bool) -> Verdict:
    ok = plan_defined and rota_set and runbooks
    return Verdict("S5-oncall", ok,
                   f"plan={plan_defined} rota={rota_set} runbooks={runbooks}", {})


def unified_launch(strategy: dict, llm: dict, shared: list[Verdict]) -> dict:
    s_failed = strategy.get("failed", [])
    l_failed = llm.get("failed", [])
    sh_failed = [c.check for c in shared if not c.ok]
    failed = s_failed + l_failed + sh_failed
    critical = bool(strategy.get("critical_block") or llm.get("critical_block"))
    launch = not failed and not critical
    return {"launch": launch, "failed": failed, "critical_block": critical,
            "strategy_hash": strategy.get("hash"), "llm_hash": llm.get("hash"),
            "hash": hashlib.sha256(json.dumps(
                [strategy.get("hash"), llm.get("hash"),
                 [(c.check, c.ok) for c in shared]]).encode()).hexdigest()[:12]}


def unified_launch_or_raise(strategy: dict, llm: dict, shared: list[Verdict]) -> dict:
    """Enforcing variant of unified_launch: returns the verdict dict on
    launch, raises RuntimeError naming every failed gate otherwise."""
    verdict = unified_launch(strategy, llm, shared)
    if not verdict["launch"]:
        raise RuntimeError(
            "launch refused: failed gates "
            f"{verdict['failed']} critical_block={verdict['critical_block']}")
    return verdict


__all__ = ["Verdict", "check_signoff", "check_docs", "check_monitoring",
           "check_killswitch", "check_oncall", "unified_launch",
           "unified_launch_or_raise"]
