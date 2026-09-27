from __future__ import annotations

from decimal import Decimal


def zscore_rank(values: dict[str, Decimal]) -> dict[str, Decimal]:
    """Cross-sectional z-scores mapped through a logistic to [0,1]."""
    if not values:
        raise ValueError("empty cross-section.")
    import math

    xs = {k: float(v) for k, v in values.items()}
    mean = sum(xs.values()) / len(xs)
    var = sum((v - mean) ** 2 for v in xs.values()) / len(xs)
    std = var ** 0.5 or 1e-12
    return {k: Decimal(str(1.0 / (1.0 + math.exp(-(v - mean) / std)))) for k, v in xs.items()}


def value_factor(pe: dict[str, Decimal]) -> dict[str, Decimal]:
    """Earnings yield (1/PE) ranked to [0,1]; higher = cheaper."""
    if not pe:
        raise ValueError("empty cross-section.")
    ey = {k: (1.0 / float(v) if float(v) > 0 else 0.0) for k, v in pe.items()}
    lo, hi = min(ey.values()), max(ey.values())
    if hi == lo:
        return {k: Decimal("0.5") for k in ey}
    return {k: Decimal(str((v - lo) / (hi - lo))) for k, v in ey.items()}


def quality_factor(roe: dict[str, Decimal], accruals: dict[str, Decimal]) -> dict[str, Decimal]:
    """Quality = ROE rank minus accruals rank, rescaled to [0,1]."""
    if set(roe) != set(accruals) or not roe:
        raise ValueError("roe/accruals must align and be non-empty.")

    def rank(d: dict[str, Decimal]) -> dict[str, float]:
        ordered = sorted(d, key=lambda k: float(d[k]))
        return {k: i / max(len(d) - 1, 1) for i, k in enumerate(ordered)}

    rr, ar = rank(roe), rank(accruals)
    return {k: Decimal(str((rr[k] - ar[k] + 1.0) / 2.0)) for k in roe}


def size_factor(market_cap: dict[str, Decimal]) -> dict[str, Decimal]:
    """Small-minus-big: inverted log-cap rank in [0,1]."""
    if not market_cap:
        raise ValueError("empty cross-section.")
    import math

    lc = {k: math.log(max(float(v), 1.0)) for k, v in market_cap.items()}
    lo, hi = min(lc.values()), max(lc.values())
    if hi == lo:
        return {k: Decimal("0.5") for k in lc}
    return {k: Decimal(str(1.0 - (v - lo) / (hi - lo))) for k, v in lc.items()}


def low_vol_factor(vol: dict[str, Decimal]) -> dict[str, Decimal]:
    """Low-volatility: inverted rank in [0,1]."""
    if not vol:
        raise ValueError("empty cross-section.")
    lo, hi = min(float(v) for v in vol.values()), max(float(v) for v in vol.values())
    if hi == lo:
        return {k: Decimal("0.5") for k in vol}
    return {k: Decimal(str(1.0 - (float(v) - lo) / (hi - lo))) for k, v in vol.items()}


def combine_factors(
    factors: tuple[dict[str, Decimal], ...], weights: tuple[Decimal, ...] | None = None
) -> dict[str, Decimal]:
    """Weighted average of aligned factor maps. Deterministic, fail-closed."""
    if not factors:
        raise ValueError("need at least one factor.")
    keys = set(factors[0])
    if any(set(f) != keys for f in factors):
        raise ValueError("factor maps must align.")
    w = list(weights) if weights is not None else [Decimal("1")] * len(factors)
    if len(w) != len(factors):
        raise ValueError("weights must align with factors.")
    tot = sum(w) or Decimal("1")
    return {
        k: sum(f[k] * wi for f, wi in zip(factors, w)) / tot for k in sorted(keys)
    }
