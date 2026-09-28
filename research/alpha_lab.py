"""W191-W210 (D) — Alpha research: formal alpha record, orthogonalization,
decay laboratory, capacity ladder $10K->$500M.

Every alpha gets an immutable ID (ALPHA-<FAMILY>-<NNNNN>).
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field

CAPITAL_LADDER: tuple[float, ...] = (10_000, 100_000, 1_000_000, 10_000_000,
                                     50_000_000, 100_000_000, 500_000_000)


def _hash(obj: object) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()[:12]


@dataclass(frozen=True, slots=True)
class AlphaRecord:
    alpha_id: str  # ALPHA-MOM-00471
    hypothesis: str
    math_def: str
    universe: tuple[str, ...]
    features: tuple[str, ...]
    neutralization: str
    signal: str
    holding_period_bars: int
    record_hash: str

    @staticmethod
    def create(family: str, seq: int, **kwargs) -> "AlphaRecord":
        aid = f"ALPHA-{family.upper()}-{seq:05d}"
        h = _hash((aid, kwargs.get("hypothesis"), kwargs.get("math_def")))
        return AlphaRecord(aid, kwargs.get("hypothesis", ""), kwargs.get("math_def", ""),
                           tuple(kwargs.get("universe", ())), tuple(kwargs.get("features", ())),
                           kwargs.get("neutralization", "none"), kwargs.get("signal", ""),
                           int(kwargs.get("holding_period_bars", 1)), h)


def pairwise_corr(a: list[float], b: list[float]) -> float:
    n = min(len(a), len(b))
    if n < 2:
        return 0.0
    ma, mb = sum(a[:n]) / n, sum(b[:n]) / n
    da = math.sqrt(sum((x - ma) ** 2 for x in a[:n]))
    db = math.sqrt(sum((x - mb) ** 2 for x in b[:n]))
    if da <= 0 or db <= 0:
        return 0.0
    return sum((x - ma) * (y - mb) for x, y in zip(a[:n], b[:n])) / (da * db)


def mutual_info_hist(a: list[float], b: list[float], bins: int = 8) -> float:
    """Histogram MI estimate (nats); coarse but deterministic and auditable."""
    n = min(len(a), len(b))
    if n < 4:
        return 0.0
    aa, bb = a[:n], b[:n]
    lo_a, hi_a = min(aa), max(aa)
    lo_b, hi_b = min(bb), max(bb)
    if hi_a == lo_a or hi_b == lo_b:
        return 0.0
    joint = [[0] * bins for _ in range(bins)]
    for x, y in zip(aa, bb):
        i = min(bins - 1, int((x - lo_a) / (hi_a - lo_a) * bins))
        j = min(bins - 1, int((y - lo_b) / (hi_b - lo_b) * bins))
        joint[i][j] += 1
    mi = 0.0
    for i in range(bins):
        for j in range(bins):
            pxy = joint[i][j] / n
            if not pxy:
                continue
            px = sum(joint[i]) / n
            py = sum(joint[r][j] for r in range(bins)) / n
            mi += pxy * math.log(pxy / (px * py))
    return mi


def orthogonalize(signals: dict[str, list[float]]) -> dict[str, list[float]]:
    """Gram-Schmidt over alpha panel -> orthogonal basis (residual information)."""
    names = sorted(signals)
    basis: dict[str, list[float]] = {}
    for nm in names:
        v = list(signals[nm])
        for onm in names:
            if onm == nm or onm not in basis:
                continue
            u = basis[onm]
            n = min(len(v), len(u))
            num = sum(v[i] * u[i] for i in range(n))
            den = sum(x * x for x in u[:n]) or 1.0
            for i in range(n):
                v[i] -= num / den * u[i]
        basis[nm] = v
    return basis


@dataclass
class DecayLab:
    """IC/PnL/capacity/crowding decay across horizons; half-life via log fit."""

    horizons: tuple[int, ...] = (1, 5, 30, 60, 390, 1950, 7800)  # bars: 1m..1mo approx

    def decay_curve(self, ic_by_horizon: list[float]) -> dict:
        import math as _m
        # fit ic = a * exp(-h / tau)
        xs = [h for h, v in zip(self.horizons, ic_by_horizon) if v > 0]
        ys = [v for v in ic_by_horizon if v > 0]
        if len(xs) < 2:
            return {"half_life_bars": 0.0, "curve": list(ic_by_horizon)}
        lx, ly = [_m.log(h) for h in xs], [_m.log(v) for v in ys]
        mx, my = sum(lx) / len(lx), sum(ly) / len(ly)
        den = sum((x - mx) ** 2 for x in lx) or 1.0
        slope = sum((x - mx) * (y - my) for x, y in zip(lx, ly)) / den
        tau = -1.0 / slope if slope < 0 else float("inf")
        return {"half_life_bars": tau * _m.log(2) if tau != float("inf") else float("inf"),
                "curve": list(ic_by_horizon)}


@dataclass(frozen=True, slots=True)
class CapacityPoint:
    capital: float
    gross_bps: float
    net_bps: float
    sharpe: float
    drawdown: float


def capacity_ladder(gross_bps: float, adv_usd: float, turnover: float = 1.0,
                    sharpe_gross: float = 1.0, dd_gross: float = 0.05) -> list[CapacityPoint]:
    """Net economics per rung under sqrt impact; answers 'where does it stop working?'."""
    out: list[CapacityPoint] = []
    for cap in CAPITAL_LADDER:
        part = cap * turnover / max(adv_usd, 1e-9)
        cost = 50.0 * math.sqrt(min(part, 1.0)) * turnover
        net = gross_bps - cost
        scale = max(net, 0.0) / max(gross_bps, 1e-9)
        out.append(CapacityPoint(cap, gross_bps, net, sharpe_gross * math.sqrt(scale),
                                 dd_gross / max(scale, 0.2)))
    return out


def economic_limit(points: list[CapacityPoint], min_sharpe: float = 0.5) -> float:
    for p in points:
        if p.sharpe < min_sharpe or p.net_bps <= 0:
            return p.capital
    return points[-1].capital * 2  # beyond ladder: report as such, honestly
