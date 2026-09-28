"""Capacity curves: expected implementation cost vs deployed capital.

Real math (not multipliers): per-capital participation -> Almgren-Chriss
sqrt impact + spread + fees, summed over the traded universe. Answers "how
much capital before costs eat the edge" for $1M/$10M/$50M/$100M.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CapacityPoint:
    capital: float
    participation: float
    impact_bps: float
    spread_bps: float
    fee_bps: float
    total_cost_bps: float


def capacity_curve(edge_bps: float, adv_shares: float, price: float,
                   daily_turnover: float = 1.0, spread_bps: float = 5.0,
                   fee_bps: float = 1.0, gamma: float = 0.5,
                   capitals: tuple[float, ...] = (1e6, 10e6, 50e6, 100e6)) -> list[CapacityPoint]:
    """Cost at each capital level for a strategy with `edge_bps` per unit turnover.

    position_shares = capital * turnover / price; participation = shares/ADV;
    impact = gamma * sigma_proxy * sqrt(participation) with sigma_proxy=200bps
    daily-scale (documented proxy; calibrate per asset for production).
    """
    if edge_bps <= 0 or adv_shares <= 0 or price <= 0:
        raise ValueError("edge_bps, adv_shares and price must be positive.")
    out = []
    for capital in capitals:
        shares = capital * daily_turnover / price
        part = shares / adv_shares
        impact = gamma * 200.0 * (part ** 0.5)
        total = impact + spread_bps / 2 + fee_bps
        out.append(CapacityPoint(capital, part, impact, spread_bps / 2, fee_bps, total))
    return out


def max_capacity(edge_bps: float, **kwargs) -> float:
    """Largest capital where total cost < edge (linear interp on the curve)."""
    curve = capacity_curve(edge_bps, **kwargs)
    prev = 0.0
    for pt in curve:
        if pt.total_cost_bps >= edge_bps:
            return prev
        prev = pt.capital
    return curve[-1].capital
