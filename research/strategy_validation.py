"""Strategy launch validation — 11 checks (fail-closed, deterministic).

Each check returns Verdict(pass, evidence, detail). No fake live data:
paper/live paths require explicit badges; synthetic is labelled.
Critical gate: Monte Carlo / parameter perturbation kills edge -> DO NOT LAUNCH.
"""
from __future__ import annotations

import hashlib
import json
import math
import random
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Verdict:
    check: str
    ok: bool
    evidence: str
    detail: dict = field(default_factory=dict)


def _sharpe(returns: list[float]) -> float:
    n = len(returns)
    if n < 2:
        return 0.0
    m = sum(returns) / n
    v = sum((r - m) ** 2 for r in returns) / (n - 1)
    return m / math.sqrt(v) * math.sqrt(252) if v > 0 else 0.0


def _max_dd(equity: list[float]) -> float:
    peak, dd = equity[0] if equity else 1.0, 0.0
    for e in equity:
        peak = max(peak, e)
        dd = max(dd, (peak - e) / peak if peak else 0.0)
    return dd


def _skew(xs: list[float]) -> float:
    n = len(xs)
    if n < 3:
        return 0.0
    m = sum(xs) / n
    s = math.sqrt(sum((x - m) ** 2 for x in xs) / n) or 1e-9
    return sum(((x - m) / s) ** 3 for x in xs) / n


# 1 — OOS: >=20-30% never used in development
def check_oos(n_total: int, n_oos: int, oos_sharpe: float, min_frac: float = 0.20) -> Verdict:
    frac = n_oos / max(1, n_total)
    ok = frac >= min_frac and oos_sharpe > 0
    return Verdict("1-oos", ok, f"oos_frac={frac:.2f} sharpe={oos_sharpe:.2f}",
                   {"frac": frac, "oos_sharpe": oos_sharpe})


# 2 — Walk-forward rolling windows
def check_walkforward(window_sharpes: list[float], min_win_rate: float = 0.5) -> Verdict:
    if not window_sharpes:
        return Verdict("2-walkforward", False, "no windows", {})
    wr = sum(1 for s in window_sharpes if s > 0) / len(window_sharpes)
    ok = wr >= min_win_rate and sum(window_sharpes) / len(window_sharpes) > 0
    return Verdict("2-walkforward", ok, f"win_rate={wr:.2f} n={len(window_sharpes)}",
                   {"win_rate": wr})


# 3 — Overfitting: param sensitivity + Monte Carlo / block bootstrap
def check_overfit(base_sharpe: float, perturbed_sharpes: list[float],
                  mc_sharpes: list[float], tol: float = 0.5) -> Verdict:
    """Small param changes shouldn't kill edge; MC 5th pct must stay > 0."""
    if not perturbed_sharpes or not mc_sharpes:
        return Verdict("3-overfit", False, "missing perturbation/MC", {})
    worst_param = min(perturbed_sharpes)
    mc_sorted = sorted(mc_sharpes)
    p5 = mc_sorted[max(0, int(0.05 * len(mc_sorted)))]
    ok = worst_param > base_sharpe * (1 - tol) and worst_param > 0 and p5 > 0
    return Verdict("3-overfit", ok,
                   f"base={base_sharpe:.2f} worst_param={worst_param:.2f} mc_p5={p5:.2f}",
                   {"worst_param": worst_param, "mc_p5": p5,
                    "critical": "edge disappears under perturbation -> DO NOT LAUNCH"})


def block_bootstrap(trades: list[float], n_iter: int = 200,
                    block: int = 10, seed: int = 7) -> list[float]:
    rng = random.Random(seed)
    n = len(trades)
    out = []
    for _ in range(n_iter):
        sample = []
        while len(sample) < n:
            i = rng.randrange(max(1, n - block + 1))
            sample.extend(trades[i:i + block])
        sample = sample[:n]
        m = sum(sample) / n
        v = sum((x - m) ** 2 for x in sample) / max(1, n - 1) or 1e-12
        out.append(m / math.sqrt(v) * math.sqrt(252))
    return out


# 4 — Look-ahead: PIT chain enforcement
def check_pit(chain_ok: bool, restated_used: bool) -> Verdict:
    ok = chain_ok and not restated_used
    return Verdict("4-lookahead", ok,
                   "t_event<=t_pub<=t_avail<=t_dec<=t_exec, no restatements"
                   if ok else "PIT violated or restated financials used", {})


# 5 — Survivorship: delisted included
def check_survivorship(n_listed: int, n_delisted: int) -> Verdict:
    ok = n_delisted > 0 and (n_delisted / max(1, n_listed + n_delisted)) >= 0.05
    return Verdict("5-survivorship", ok,
                   f"delisted={n_delisted} listed={n_listed}", {})


# 6 — Costs at 1.5-2x
def check_costs(net_base: float, net_15x: float, net_20x: float) -> Verdict:
    ok = net_base > 0 and net_15x > 0 and net_20x > 0
    return Verdict("6-costs", ok,
                   f"net@{1}x={net_base:.1f} @{1.5}x={net_15x:.1f} @{2}x={net_20x:.1f}bps",
                   {"net_2x": net_20x})


# 7 — Regime stress: bull/bear/high-vol incl 2008/2020/2022
def check_regimes(per_regime: dict[str, float]) -> Verdict:
    required = {"bull", "bear", "highvol", "2008", "2020", "2022"}
    missing = required - set(per_regime)
    ok = not missing and all(v > -0.05 for v in per_regime.values())
    return Verdict("7-regimes", ok,
                   f"regimes={sorted(per_regime)} missing={sorted(missing)}",
                   {"per_regime": per_regime})


# 8 — Risk metrics
def check_risk(returns: list[float], equity: list[float],
               sharpe_min: float = 0.5, dd_max: float = 0.25) -> Verdict:
    s = _sharpe(returns)
    dd = _max_dd(equity)
    ann = sum(returns) / len(returns) * 252 if returns else 0.0
    calmar = (ann / dd) if dd > 1e-12 else (float("inf") if ann > 0 else 0.0)
    sk = _skew(returns)
    ok = s >= sharpe_min and dd <= dd_max and calmar > 0.5 and sk > -1.5
    return Verdict("8-risk", ok, f"sharpe={s:.2f} dd={dd:.2%} calmar={calmar:.2f} skew={sk:.2f}",
                   {"sharpe": s, "max_dd": dd, "calmar": calmar, "skew": sk})


# 9 — Paper trading: >= one full market cycle w/ real flow/latency/slippage
def check_paper(days: int, fills: int, source: str, min_days: int = 60) -> Verdict:
    ok = days >= min_days and fills > 0 and source in ("live-paper", "paper-broker")
    return Verdict("9-paper", ok, f"days={days} fills={fills} source={source}",
                   {"days": days, "fills": fills})


# 10 — Data quality: multi-provider cross-validation, no gaps/tz/skew
def check_data_quality(providers: int, gaps: int, tz_ok: bool, max_skew_ms: float) -> Verdict:
    ok = providers >= 2 and gaps == 0 and tz_ok and max_skew_ms <= 1000
    return Verdict("10-data", ok,
                   f"providers={providers} gaps={gaps} tz_ok={tz_ok} skew_ms={max_skew_ms}",
                   {})


# 11 — Compliance & execution
def check_compliance(kill_tested: bool, limits_set: bool, routing_ok: bool,
                     regulatory_ok: bool) -> Verdict:
    ok = kill_tested and limits_set and routing_ok and regulatory_ok
    return Verdict("11-compliance", ok,
                   f"kill={kill_tested} limits={limits_set} routing={routing_ok} reg={regulatory_ok}",
                   {})


def launch_verdict(checks: list[Verdict]) -> dict:
    failed = [c.check for c in checks if not c.ok]
    # Critical gate: check 3 carries do-not-launch authority
    c3 = next((c for c in checks if c.check == "3-overfit"), None)
    critical_block = c3 is not None and not c3.ok
    return {"launch": not failed and not critical_block,
            "failed": failed, "critical_block": critical_block,
            "hash": hashlib.sha256(json.dumps(
                [(c.check, c.ok) for c in checks]).encode()).hexdigest()[:12]}


__all__ = ["Verdict", "check_oos", "check_walkforward", "check_overfit",
           "block_bootstrap", "check_pit", "check_survivorship", "check_costs",
           "check_regimes", "check_risk", "check_paper", "check_data_quality",
           "check_compliance", "launch_verdict"]
