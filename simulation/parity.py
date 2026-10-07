"""Stage-4 S: sim == backtest parity harness at identical costs.

Runs the same fill logic (spread + fee_bps + impact) through both paths and
asserts identical P&L within tolerance. Any divergence is a fidelity bug.
"""
from __future__ import annotations


def simulate_fills(prices: list[float], qty: float, *, spread: float = 0.01,
                   fee_bps: float = 1.0, impact_bps: float = 0.0) -> float:
    pnl = 0.0
    for px in prices:
        cost = px * (fee_bps + impact_bps) / 1e4 + spread / 2.0
        pnl += qty * px - cost * abs(qty)
    return pnl


def assert_parity(path_a: float, path_b: float, tol: float = 1e-9) -> None:
    if abs(path_a - path_b) > tol:
        raise ValueError(f"sim/backtest parity violated: {path_a} vs {path_b} (tol {tol})")


__all__ = ["simulate_fills", "assert_parity"]
