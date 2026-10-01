"""W130 — Empirical Transaction-Cost Engine.

spread + impact (sqrt, calibrated) + fees + borrow + delay.
Calibrated from fills; deterministic; fail-closed on missing inputs.
"""
from __future__ import annotations

from dataclasses import dataclass

from simulation.l3_engine import SquareRootImpact


@dataclass(frozen=True, slots=True)
class CostBreakdown:
    spread_bps: float
    impact_bps: float
    fee_bps: float
    borrow_bps: float
    delay_bps: float
    total_bps: float


@dataclass
class TransactionCostEngine:
    fee_bps: float = 0.5
    borrow_bps_annual: float = 50.0
    gamma: float = 0.5
    half_spread_bps: float = 1.0
    calibrated: bool = False  # Stream C: True only after empirical fill calibration
    calibration_id: str = "proxy-uncalibrated"

    def quote(self, *, qty: float, adv: float, sigma: float, spread_bps: float | None = None,
              side: str = "buy", hold_days: float = 0.0, short: bool = False) -> CostBreakdown:
        sp = self.half_spread_bps if spread_bps is None else spread_bps / 2.0
        imp = SquareRootImpact(self.gamma).estimate(abs(qty), adv, sigma).total_bps
        borrow = (self.borrow_bps_annual * hold_days / 365.0) if short else 0.0
        total = sp + imp + self.fee_bps + borrow
        return CostBreakdown(sp, imp, self.fee_bps, borrow, 0.0, total)

    def net_alpha_bps(self, gross_bps: float, cost: CostBreakdown, turnover: float = 1.0) -> float:
        return gross_bps - cost.total_bps * turnover

    def breakeven_turnover(self, gross_bps: float, cost: CostBreakdown) -> float:
        if cost.total_bps <= 0:
            return float("inf")
        return gross_bps / cost.total_bps
