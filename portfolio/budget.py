"""Risk budgeting: inverse-vol parity + risk contributions + group caps."""
from __future__ import annotations

from decimal import Decimal
from typing import Mapping


def risk_parity_weights(vols: Mapping[str, Decimal]) -> dict[str, Decimal]:
    """Inverse-volatility weights normalized to 1. Fail-closed on bad input."""
    if not vols:
        raise ValueError("vols cannot be empty.")
    inv: dict[str, Decimal] = {}
    for asset, vol in vols.items():
        if vol <= 0:
            raise ValueError(f"non-positive vol for {asset}.")
        inv[asset] = Decimal("1") / vol
    total = sum(inv.values(), Decimal("0"))
    return {a: w / total for a, w in inv.items()}


def risk_contribution(weights: Mapping[str, Decimal], vols: Mapping[str, Decimal]) -> dict[str, Decimal]:
    """Independent-vol risk share per asset (sums to portfolio vol)."""
    if set(weights) != set(vols):
        raise ValueError("weights and vols must cover the same assets.")
    port_vol = sum((abs(weights[a]) * vols[a] for a in weights), Decimal("0"))
    if port_vol == 0:
        raise ValueError("zero portfolio vol.")
    return {a: abs(weights[a]) * vols[a] / port_vol for a in weights}


def check_group_caps(
    weights: Mapping[str, Decimal],
    groups: Mapping[str, str],
    caps: Mapping[str, Decimal],
) -> tuple[str, ...]:
    """Return breached group names where |group weight| exceeds cap."""
    totals: dict[str, Decimal] = {}
    for asset, weight in weights.items():
        group = groups.get(asset, "other")
        totals[group] = totals.get(group, Decimal("0")) + abs(weight)
    return tuple(sorted(g for g, total in totals.items() if g in caps and total > caps[g]))
