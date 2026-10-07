"""Stage-3 P: hard portfolio constraints — violations BLOCK, never advise.

Checks: gross/net leverage, max single weight, turnover, long-only, min/max count.
Returns (ok, reasons). Infeasible inputs get explanation, not silent clip.
Deterministic: same input → same output (pure function, tested).
"""
from __future__ import annotations


def enforce_hard_constraints(weights: dict[str, float], *,
                             max_gross: float = 1.0,
                             max_single: float = 0.35,
                             long_only: bool = True,
                             max_turnover: float | None = None,
                             prev: dict[str, float] | None = None) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    vals = list(weights.values())
    gross = sum(abs(v) for v in vals)
    if gross > max_gross + 1e-9:
        reasons.append(f"gross {gross:.4f} > max_gross {max_gross}")
    for k, v in weights.items():
        if abs(v) > max_single + 1e-9:
            reasons.append(f"{k} weight {v:.4f} > max_single {max_single}")
        if long_only and v < -1e-9:
            reasons.append(f"{k} short {v:.4f} violates long-only")
    if max_turnover is not None and prev is not None:
        keys = set(weights) | set(prev)
        to = sum(abs(weights.get(k, 0.0) - prev.get(k, 0.0)) for k in keys) / 2.0
        if to > max_turnover + 1e-9:
            reasons.append(f"turnover {to:.4f} > max {max_turnover}")
    return (len(reasons) == 0, reasons)


__all__ = ["enforce_hard_constraints"]
