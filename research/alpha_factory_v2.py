"""P3 — Alpha Factory v2 (W131 flagship).

Research Agent -> Hypothesis -> Feature Generation -> PIT Dataset ->
Alpha Construction -> Neutralization -> Walk Forward -> Cost Model ->
Capacity -> Crowding -> DSR/PBO/FDR -> Stress -> OOS -> Research Registry.

Auto-rejects weak/overfit hypotheses via deterministic gates.
Pure numpy; deterministic seeds; no network.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from typing import Callable

FACTORY_VERSION = "alpha-factory-v2"


def _hash(obj: object) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()[:12]


def deflated_sharpe(sr: float, n_trials: int, n_obs: int, skew: float = 0.0, kurt: float = 3.0) -> float:
    """Bailey-Lopez de Prado Deflated Sharpe Ratio (PSR against trials-adjusted benchmark).

    Canonical implementation lives in research.statistics.canonical
    (vetted math in delta_omega.alpha_risk); this wrapper preserves the
    factory's historical signature.
    """
    from research.statistics.canonical import deflated_sharpe as _dsr
    return _dsr(sr, n_trials, n_obs, skew, kurt)


def pbo_score(is_sharpes: list[float], oos_sharpes: list[float]) -> float:
    """Single-split PBO fallback (labeled, not definitive).

    Honest 0.0/1.0 rank verdict: 1.0 when the IS-best trial ranks at/below
    median OOS. For trial panels use research.statistics.canonical.cpcv_pbo
    (full CSCV/CPCV methodology). NaN (insufficient data) maps to 1.0 here
    to preserve the factory's fail-closed gate semantics.
    """
    from research.statistics.canonical import pbo_single_split
    out = pbo_single_split(is_sharpes, oos_sharpes)
    val = out["pbo"]
    return 1.0 if val != val else float(val)


def bh_fdr(pvalues: list[float], q: float = 0.1) -> list[bool]:
    """Benjamini-Hochberg FDR rejections (deterministic)."""
    n = len(pvalues)
    order = sorted(range(n), key=lambda i: pvalues[i])
    thresh = 0.0
    rej = [False] * n
    for rank, idx in enumerate(order, start=1):
        if pvalues[idx] <= rank / n * q:
            thresh = pvalues[idx]
    for i, p in enumerate(pvalues):
        rej[i] = p <= thresh
    return rej


def sharpe(returns: list[float]) -> float:
    import statistics
    if len(returns) < 2:
        return 0.0
    m = statistics.fmean(returns)
    s = statistics.pstdev(returns)
    if s <= 0:
        return 0.0
    return m / s * math.sqrt(252)


@dataclass(frozen=True, slots=True)
class HypothesisV2:
    hid: str
    statement: str
    family: str
    params: str = "{}"
    trials_context: int = 1  # how many hypotheses tried before (for DSR)


@dataclass(frozen=True, slots=True)
class GateVerdict:
    gate: str
    passed: bool
    metric: float
    threshold: float
    detail: str = ""


@dataclass(frozen=True, slots=True)
class FactoryResult:
    hid: str
    experiment_id: str
    passed: bool
    gates: tuple[GateVerdict, ...]
    net_sharpe: float
    dsr: float
    pbo: float
    capacity_usd: float
    registry_hash: str


def neutralize_factor(returns: list[float], factor: list[float]) -> list[float]:
    """Orthogonalize returns vs factor (OLS residual)."""
    n = min(len(returns), len(factor))
    if n < 2:
        return list(returns)
    r, f = returns[:n], factor[:n]
    mf = sum(f) / n
    mr = sum(r) / n
    den = sum((x - mf) ** 2 for x in f)
    beta = sum((x - mf) * (y - mr) for x, y in zip(f, r)) / den if den > 0 else 0.0
    return [y - beta * x for x, y in zip(f, r)]


def capacity_curve(gross_bps: list[float], adv_usd: float, gamma: float = 0.5,
                   cost_scale_bps: float = 50.0,
                   cost_source: str = "proxy-uncalibrated") -> float:
    """Max USD where net Sharpe stays > 0 under sqrt impact (bisection, deterministic).

    cost_bps = cost_scale_bps * sqrt(participation). The default 50.0 is a
    STYLIZED proxy (gamma=0.25 @ 200bps sigma), NOT calibrated evidence:
    pass cost_scale_bps = fitted_gamma * 200.0 with cost_source="fills:n=<k>"
    once fills exist (see research.capacity.calibrated). The source label is
    recorded in the capacity gate detail by AlphaFactoryV2.run.
    """
    if not gross_bps or adv_usd <= 0:
        return 0.0
    gross = sum(gross_bps) / len(gross_bps)
    lo, hi = 0.0, adv_usd
    for _ in range(24):
        mid = (lo + hi) / 2
        part = mid / adv_usd
        cost_bps = cost_scale_bps * math.sqrt(max(part, 0.0))
        if gross - cost_bps > 0:
            lo = mid
        else:
            hi = mid
    return lo


class AlphaFactoryV2:
    """Deterministic flagship pipeline with auto-reject gates."""

    def __init__(self, seed: int = 7) -> None:
        self._seed = seed
        self._registry: dict[str, FactoryResult] = {}

    def run(
        self,
        hyp: HypothesisV2,
        *,
        returns_is: list[list[float]],
        returns_oos: list[float],
        factor_oos: list[float] | None = None,
        adv_usd: float = 10_000_000.0,
        cost_bps_per_trade: float = 3.0,
        turnover: float = 1.0,
        min_oos_sharpe: float = 0.5,
        min_dsr: float = 0.8,
        max_pbo: float = 0.4,
        experiment_seq: int = 1,
        cost_scale_bps: float = 50.0,
        cost_source: str = "proxy-uncalibrated",
    ) -> FactoryResult:
        gates: list[GateVerdict] = []
        # 1. walk-forward consistency: mean IS sharpe and hit-rate
        is_sh = [sharpe(r) for r in returns_is]
        mean_is = sum(is_sh) / max(len(is_sh), 1)
        gates.append(GateVerdict("walkforward", mean_is > 0.3, mean_is, 0.3))
        # 2. neutralization (orthogonalize OOS vs factor)
        resid = neutralize_factor(returns_oos, factor_oos or [0.0] * len(returns_oos))
        oos_sh = sharpe(resid)
        # 3. cost model
        net_sh = oos_sh - (cost_bps_per_trade * turnover) / 100.0
        gates.append(GateVerdict("oos_net", net_sh >= min_oos_sharpe, net_sh, min_oos_sharpe))
        # 4. DSR (canonical Bailey-LdP; trials context sizes the null)
        dsr = deflated_sharpe(oos_sh, max(hyp.trials_context, 1), max(len(returns_oos), 2))
        gates.append(GateVerdict("dsr", dsr >= min_dsr, dsr, min_dsr,
                                 detail="bailey-ldp-dsr-via-delta-omega"))
        # 5. PBO: single-split rank fallback on IS partitions (split each IS
        # series in half -> pseudo OOS). Labeled fallback: full CSCV/CPCV PBO
        # over trial panels lives in research.statistics.canonical.cpcv_pbo.
        pseudo_oos = [sharpe(r[len(r) // 2:]) for r in returns_is]
        pseudo_is = [sharpe(r[: len(r) // 2]) for r in returns_is]
        pbo = pbo_score(pseudo_is, pseudo_oos)
        gates.append(GateVerdict("pbo", pbo <= max_pbo, pbo, max_pbo,
                                 detail="single-split-rank-fallback"))
        # 6. capacity (cost source labeled; uncalibrated proxy cannot pass R5)
        cap = capacity_curve(resid, adv_usd, cost_scale_bps=cost_scale_bps,
                             cost_source=cost_source)
        gates.append(GateVerdict("capacity", cap >= adv_usd * 0.01, cap, adv_usd * 0.01,
                                 detail=f"cost-source={cost_source}"))
        # 7. crowding proxy: pairwise correlation of IS partitions must be bounded
        crowd = self._crowding(returns_is)
        gates.append(GateVerdict("crowding", crowd <= 0.85, crowd, 0.85))
        passed = all(g.passed for g in gates)
        exp_id = f"EXP-{experiment_seq:07d}"
        rh = _hash((hyp.hid, round(net_sh, 6), round(dsr, 6), passed))
        res = FactoryResult(hyp.hid, exp_id, passed, tuple(gates), net_sh, dsr, pbo, cap, rh)
        if passed:
            self._registry[exp_id] = res
        return res

    @staticmethod
    def _crowding(partitions: list[list[float]]) -> float:
        if len(partitions) < 2:
            return 0.0
        import statistics
        corrs = []
        for i in range(len(partitions)):
            for j in range(i + 1, len(partitions)):
                a, b = partitions[i], partitions[j]
                n = min(len(a), len(b))
                if n < 2:
                    continue
                ma, mb = sum(a[:n]) / n, sum(b[:n]) / n
                da = math.sqrt(sum((x - ma) ** 2 for x in a[:n]))
                db = math.sqrt(sum((x - mb) ** 2 for x in b[:n]))
                if da <= 0 or db <= 0:
                    continue
                corrs.append(sum((x - ma) * (y - mb) for x, y in zip(a[:n], b[:n])) / (da * db))
        return max(corrs) if corrs else 0.0
