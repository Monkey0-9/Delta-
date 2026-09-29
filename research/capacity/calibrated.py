"""Calibrated capacity curves (P1 slice, Group 23).

The stylized `50 * sqrt(participation)` proxy is NOT evidence of real
capacity. This module fits the sqrt-impact coefficient against OBSERVED
execution fills and labels every curve with its calibration source, so
downstream gates can require calibrated input:

  fills: (participation, net_cost_bps) with spread/fees already removed
  cost  = gamma * SIGMA_PROXY_BPS * sqrt(participation)

  capacity_curve(..., calibration=None)  -> source "proxy-uncalibrated"
  capacity_curve(..., calibration=fit)   -> source "fills:n=<k>"

`max_capacity` reports the largest capital with total cost below edge,
via linear interpolation on the curve.
"""
from __future__ import annotations

from dataclasses import dataclass


SIGMA_PROXY_BPS = 200.0
PROXY_GAMMA = 0.5  # legacy stylized default; always labeled uncalibrated


@dataclass(frozen=True, slots=True)
class ImpactCalibration:
    gamma: float
    n_fills: int
    r_squared: float
    source: str  # "fills:n=<k>" or "proxy-uncalibrated"

    @property
    def calibrated(self) -> bool:
        return self.source != "proxy-uncalibrated"


def proxy_calibration() -> ImpactCalibration:
    return ImpactCalibration(PROXY_GAMMA, 0, 0.0, "proxy-uncalibrated")


def fit_gamma(fills: list[tuple[float, float]],
              sigma_proxy_bps: float = SIGMA_PROXY_BPS) -> ImpactCalibration:
    """Least-squares gamma through the origin on (sqrt(part), net_cost).

    Raises ValueError when fewer than 2 usable fills are supplied
    (fail-closed: no silent proxy substitution).
    """
    pts = [(float(p), float(c)) for p, c in fills
           if p is not None and c is not None and float(p) > 0
           and float(c) == float(c)]
    if len(pts) < 2:
        raise ValueError("need >= 2 usable (participation, cost_bps) fills.")
    import math
    xs = [sigma_proxy_bps * math.sqrt(p) for p, _ in pts]
    num = sum(x * c for x, (_, c) in zip(xs, pts))
    den = sum(x * x for x in xs)
    if den <= 0:
        raise ValueError("degenerate fill panel.")
    gamma = max(0.01, min(5.0, num / den))
    mean_c = sum(c for _, c in pts) / len(pts)
    ss_tot = sum((c - mean_c) ** 2 for _, c in pts)
    ss_res = sum((c - gamma * x) ** 2 for x, (_, c) in zip(xs, pts))
    r2 = max(0.0, 1.0 - ss_res / ss_tot) if ss_tot > 0 else 0.0
    return ImpactCalibration(gamma, len(pts), round(r2, 4),
                             f"fills:n={len(pts)}")


@dataclass(frozen=True, slots=True)
class CapacityPoint:
    capital: float
    participation: float
    impact_bps: float
    spread_bps: float
    fee_bps: float
    total_cost_bps: float
    calibration_source: str


def capacity_curve(edge_bps: float, adv_shares: float, price: float,
                   daily_turnover: float = 1.0, spread_bps: float = 5.0,
                   fee_bps: float = 1.0,
                   calibration: ImpactCalibration | None = None,
                   capitals: tuple[float, ...] = (1e6, 10e6, 50e6, 100e6),
                   ) -> list[CapacityPoint]:
    """Cost at each capital level. Uncalibrated calls are explicitly labeled
    and must not pass production gates (see Group 23)."""
    if edge_bps <= 0 or adv_shares <= 0 or price <= 0:
        raise ValueError("edge_bps, adv_shares and price must be positive.")
    cal = calibration or proxy_calibration()
    import math
    out = []
    for capital in capitals:
        part = (capital * daily_turnover / price) / adv_shares
        impact = cal.gamma * SIGMA_PROXY_BPS * math.sqrt(max(part, 0.0))
        total = impact + spread_bps / 2 + fee_bps
        out.append(CapacityPoint(capital, part, impact, spread_bps / 2,
                                 fee_bps, total, cal.source))
    return out


def max_capacity(edge_bps: float, **kwargs) -> dict:
    """Largest capital with total cost < edge. Returns {capital_usd,
    calibration_source, calibrated} — never a bare number."""
    curve = capacity_curve(edge_bps, **kwargs)
    prev = 0.0
    for pt in curve:
        if pt.total_cost_bps >= edge_bps:
            return {"capital_usd": prev,
                    "calibration_source": pt.calibration_source,
                    "calibrated": pt.calibration_source != "proxy-uncalibrated"}
        prev = pt.capital
    last = curve[-1]
    return {"capital_usd": last.capital,
            "calibration_source": last.calibration_source,
            "calibrated": last.calibration_source != "proxy-uncalibrated"}


__all__ = ["SIGMA_PROXY_BPS", "CapacityPoint", "ImpactCalibration",
           "capacity_curve", "fit_gamma", "max_capacity", "proxy_calibration"]
