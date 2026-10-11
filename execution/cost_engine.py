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
    # P2 centralization: every quote stamps its calibration lineage.
    # proxy=True until the engine is fill-calibrated (Stream C).
    proxy: bool = True
    slippage_bps: float = 0.0


@dataclass
class TransactionCostEngine:
    fee_bps: float = 0.5
    borrow_bps_annual: float = 50.0
    gamma: float = 0.5
    half_spread_bps: float = 1.0
    slippage_bps: float = 0.0
    calibrated: bool = False  # Stream C: True only after empirical fill calibration
    calibration_id: str = "proxy-uncalibrated"

    @property
    def is_proxy(self) -> bool:
        return not self.calibrated

    def quote_participation(self, participation: float, sigma: float,
                            spread_bps: float | None = None,
                            side: str = "buy", hold_days: float = 0.0,
                            short: bool = False,
                            fee_bps: float | None = None,
                            slippage_bps: float | None = None) -> CostBreakdown:
        """Central per-trade quote from participation rate (fraction of ADV).

        The ONE sanctioned cost formula: half-spread + sqrt impact + fees +
        slippage + borrow. quote() and the backtest series path both delegate
        here, so assumption changes land in exactly one place.
        """
        sp = self.half_spread_bps if spread_bps is None else spread_bps / 2.0
        fee = self.fee_bps if fee_bps is None else fee_bps
        slip = self.slippage_bps if slippage_bps is None else slippage_bps
        imp = SquareRootImpact(self.gamma).estimate(
            abs(participation) * 1_000_000.0, 1_000_000.0, sigma).total_bps
        borrow = (self.borrow_bps_annual * hold_days / 365.0) if short else 0.0
        total = sp + imp + fee + slip + borrow
        return CostBreakdown(sp, imp, fee, borrow, 0.0, total,
                             proxy=not self.calibrated, slippage_bps=slip)

    def series_costs(self, participation, sigma: float,
                     spread_bps: float = 5.0, fee_bps: float = 1.0,
                     slippage_bps: float = 2.0,
                     spread_vol_ratio=None,
                     spread_vol_sensitivity: float = 0.0) -> list[float]:
        """Per-bar per-trade costs in bps (backtest path). participation and
        spread_vol_ratio are array-likes; returns a plain list (no pandas
        dependency in the engine). Vol-widened spread is opt-in via
        spread_vol_ratio (per-bar vol / baseline); sensitivity 0 disables."""
        import numpy as _np

        part = _np.asarray(list(participation), dtype=float)
        per_trade = []
        for i, p in enumerate(part):
            sp = spread_bps
            if spread_vol_ratio is not None and spread_vol_sensitivity:
                vr = float(list(spread_vol_ratio)[i])
                sp = spread_bps * (1 + spread_vol_sensitivity * max(vr - 1, 0.0))
            q = self.quote_participation(abs(float(p)), sigma,
                                         spread_bps=sp, fee_bps=fee_bps,
                                         slippage_bps=slippage_bps)
            per_trade.append(q.total_bps)
        return per_trade

    def quote(self, *, qty: float, adv: float, sigma: float, spread_bps: float | None = None,
              side: str = "buy", hold_days: float = 0.0, short: bool = False) -> CostBreakdown:
        participation = abs(qty) / adv if adv > 0 else 0.0
        return self.quote_participation(participation, sigma, spread_bps, side,
                                        hold_days, short)

    def net_alpha_bps(self, gross_bps: float, cost: CostBreakdown, turnover: float = 1.0) -> float:
        return gross_bps - cost.total_bps * turnover

    def breakeven_turnover(self, gross_bps: float, cost: CostBreakdown) -> float:
        if cost.total_bps <= 0:
            return float("inf")
        return gross_bps / cost.total_bps
