"""LLM launch validation — 12 checks (deterministic, no external calls).

Critical gate: if you can't answer "what changed and why did it get worse?"
for a given output -> observability isn't ready -> DO NOT LAUNCH.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Verdict:
    check: str
    ok: bool
    evidence: str
    detail: dict = field(default_factory=dict)


# 1 — Golden dataset >=50 basic / >=500 production
def check_golden(n: int, edge_cases: int, tier: str = "basic") -> Verdict:
    need = 500 if tier == "production" else 50
    ok = n >= need and edge_cases >= max(5, need // 10)
    return Verdict("L1-golden", ok, f"n={n} edge={edge_cases} need={need} tier={tier}",
                   {"n": n, "need": need})


# 2 — Automated evals above threshold
def check_evals(correctness: float, adherence: float, format_ok: float,
                thr: float = 0.8) -> Verdict:
    ok = min(correctness, adherence, format_ok) >= thr
    return Verdict("L2-evals", ok,
                   f"correct={correctness:.2f} adhere={adherence:.2f} format={format_ok:.2f} thr={thr}",
                   {})


# 3 — LLM-as-judge correlated with humans
def _pearson(a: list[float], b: list[float]) -> float:
    n = min(len(a), len(b))
    if n < 3:
        return 0.0
    ma, mb = sum(a[:n]) / n, sum(b[:n]) / n
    da = math.sqrt(sum((x - ma) ** 2 for x in a[:n]))
    db = math.sqrt(sum((x - mb) ** 2 for x in b[:n]))
    if da <= 0 or db <= 0:
        return 0.0
    return sum((a[i] - ma) * (b[i] - mb) for i in range(n)) / (da * db)


def check_judge(judge: list[float], human: list[float], min_r: float = 0.6) -> Verdict:
    r = _pearson(judge, human)
    return Verdict("L3-judge", r >= min_r, f"pearson_r={r:.2f} min={min_r}", {"r": r})


# 4 — Latency p50/p95/p99 + timeout/retry defined
def _pct(xs: list[float], q: float) -> float:
    s = sorted(xs)
    return s[min(len(s) - 1, int(q * len(s)))] if s else 0.0


def check_latency(samples_ms: list[float], timeout_ms: float,
                  retries: int, p99_budget: float = 5000.0) -> Verdict:
    p50, p95, p99 = _pct(samples_ms, .5), _pct(samples_ms, .95), _pct(samples_ms, .99)
    ok = bool(samples_ms) and p99 <= p99_budget and timeout_ms > 0 and retries >= 1
    return Verdict("L4-latency", ok, f"p50={p50:.0f} p95={p95:.0f} p99={p99:.0f}ms",
                   {"p50": p50, "p95": p95, "p99": p99})


# 5 — Cost modelling 1x/5x/10x
def check_cost(tokens_per_call: float, calls_month: float,
               price_per_1k: float, budget_month: float) -> Verdict:
    c1 = tokens_per_call / 1000 * price_per_1k * calls_month
    proj = {"1x": c1, "5x": c1 * 5, "10x": c1 * 10}
    ok = tokens_per_call > 0 and proj["10x"] <= budget_month * 10
    return Verdict("L5-cost", ok,
                   f"1x=${proj['1x']:.2f} 5x=${proj['5x']:.2f} 10x=${proj['10x']:.2f}/mo",
                   proj)


# 6 — Prompt robustness: edge/adversarial/format, no secrets in system prompt
SECRET_PAT = re.compile(r"(sk-|api[_-]?key|passwd|-----BEGIN .*PRIVATE KEY----)", re.I)


def check_prompt_robust(edge_pass: int, edge_total: int,
                        system_prompt: str) -> Verdict:
    rate = edge_pass / max(1, edge_total)
    ok = rate >= 0.9 and not SECRET_PAT.search(system_prompt or "")
    return Verdict("L6-robust", ok, f"edge_rate={rate:.2f} secrets={'ABSENT' if ok else 'FOUND'}",
                   {"rate": rate})


# 7 — Red-team: injection blocked, PII masked, no leakage
PII_PAT = re.compile(r"(\b\d{3}-\d{2}-\d{4}\b|[\w.]+@[\w.]+\.\w+|\b\d{16}\b)")


def mask_pii(text: str) -> str:
    return PII_PAT.sub("[MASKED]", text or "")


def check_redteam(injections_blocked: int, injections_total: int,
                  sample_output: str) -> Verdict:
    rate = injections_blocked / max(1, injections_total)
    leaked = bool(PII_PAT.search(sample_output or ""))
    ok = rate >= 0.95 and not leaked
    return Verdict("L7-redteam", ok, f"block_rate={rate:.2f} pii_leak={leaked}", {})


# 8 — Output validation & fallbacks: schema enforced, fallback on malformed
def check_schema(valid: int, total: int, fallback_ok: bool) -> Verdict:
    rate = valid / max(1, total)
    ok = rate >= 0.95 and fallback_ok
    return Verdict("L8-schema", ok, f"schema_rate={rate:.2f} fallback={fallback_ok}", {})


# 9 — Observability: every call traced (in/out/latency/tokens), dashboards, alerts
def check_observability(traced_frac: float, dashboards_live: bool,
                        alerts_live: bool) -> Verdict:
    ok = traced_frac >= 1.0 and dashboards_live and alerts_live
    detail = {"traced_frac": traced_frac,
              "critical": "can't explain what changed -> NOT READY" if not ok else "ready"}
    return Verdict("L9-observability", ok,
                   f"traced={traced_frac:.2f} dash={dashboards_live} alerts={alerts_live}",
                   detail)


# 10 — Resilience: backoff + secondary, ctx-overflow handled, loop cap
def check_resilience(backoff_ok: bool, secondary_ok: bool,
                     overflow_ok: bool, max_iters: int) -> Verdict:
    ok = backoff_ok and secondary_ok and overflow_ok and 1 <= max_iters <= 25
    return Verdict("L10-resilience", ok,
                   f"backoff={backoff_ok} secondary={secondary_ok} overflow={overflow_ok} maxiter={max_iters}",
                   {})


# 11 — Rollback: versions recorded, canary tested, rollback e2e tested
def check_rollback(versions_recorded: bool, canary_ok: bool,
                   rollback_tested: bool) -> Verdict:
    ok = versions_recorded and canary_ok and rollback_tested
    return Verdict("L11-rollback", ok,
                   f"versions={versions_recorded} canary={canary_ok} rollback_e2e={rollback_tested}",
                   {})


# 12 — CI eval gates: suite runs per change, regressions block
def check_ci(gates_live: bool, last_blocked: bool) -> Verdict:
    ok = gates_live  # last_blocked proves the gate has teeth (informational)
    return Verdict("L12-ci", ok, f"gates_live={gates_live} gate_has_blocked={last_blocked}",
                   {})


def launch_verdict(checks: list[Verdict]) -> dict:
    failed = [c.check for c in checks if not c.ok]
    c9 = next((c for c in checks if c.check == "L9-observability"), None)
    critical_block = c9 is not None and not c9.ok
    return {"launch": not failed and not critical_block,
            "failed": failed, "critical_block": critical_block,
            "hash": hashlib.sha256(json.dumps(
                [(c.check, c.ok) for c in checks]).encode()).hexdigest()[:12]}


__all__ = ["Verdict", "check_golden", "check_evals", "check_judge",
           "check_latency", "check_cost", "check_prompt_robust", "check_redteam",
           "mask_pii", "check_schema", "check_observability", "check_resilience",
           "check_rollback", "check_ci", "launch_verdict"]
