"""DELTA OS — Institutional Almgren-Chriss Optimal Execution Engine.

Implements the continuous and discrete Almgren-Chriss (2000) execution model:
- Balances market impact (temporary and permanent) against volatility risk.
- Closed-form optimal trading trajectory x(t) = X * sinh(kappa * (T - t)) / sinh(kappa * T).
- Dynamic adaptation to real-time volume imbalances and spread dislocations.
- Implementation shortfall and slippage decomposition.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import List, Optional, Tuple
import numpy as np


@dataclass(frozen=True, slots=True)
class AlmgrenChrissTrajectory:
    total_quantity: float
    horizon_seconds: float
    num_intervals: int
    kappa: float
    half_life_seconds: float
    expected_shortfall_bps: float
    variance_bps_sq: float
    target_holdings: Tuple[float, ...]      # Shares remaining at each interval [x_0, x_1, ..., x_N]
    slice_quantities: Tuple[float, ...]     # Child order sizes [n_1, n_2, ..., n_N]
    slice_times_sec: Tuple[float, ...]      # Timestamp of each interval [t_0, t_1, ..., t_N]


@dataclass(frozen=True, slots=True)
class AdaptiveExecutionUpdate:
    original_target_slice: float
    adapted_slice: float
    spread_penalty: float
    volume_bonus: float
    urgency_multiplier: float
    reason: str


class AlmgrenChrissExecutionEngine:
    """Optimal institutional order execution engine."""

    def __init__(
        self,
        risk_aversion: float = 1e-6,
        volatility_annual: float = 0.30,
        temporary_impact_eta: float = 2.5e-6,
        permanent_impact_gamma: float = 1.0e-7,
        annual_trading_seconds: float = 252.0 * 6.5 * 3600.0,
    ) -> None:
        if risk_aversion < 0:
            raise ValueError("risk_aversion must be non-negative")
        if volatility_annual <= 0:
            raise ValueError("volatility_annual must be positive")
        if temporary_impact_eta <= 0:
            raise ValueError("temporary_impact_eta must be positive")
        if permanent_impact_gamma < 0:
            raise ValueError("permanent_impact_gamma must be non-negative")

        self.risk_aversion = risk_aversion
        self.volatility_annual = volatility_annual
        self.temporary_impact_eta = temporary_impact_eta
        self.permanent_impact_gamma = permanent_impact_gamma
        # Convert annual volatility to per-second volatility: sigma_sec = sigma_ann / sqrt(trading_sec)
        self.volatility_sec = volatility_annual / math.sqrt(annual_trading_seconds)

    def compute_trajectory(
        self,
        total_quantity: float,
        horizon_seconds: float,
        num_intervals: int = 10,
        price: float = 100.0,
    ) -> AlmgrenChrissTrajectory:
        """Calculate the optimal Almgren-Chriss trading trajectory."""
        if total_quantity <= 0:
            raise ValueError("total_quantity must be positive")
        if horizon_seconds <= 0:
            raise ValueError("horizon_seconds must be positive")
        if num_intervals < 2:
            raise ValueError("num_intervals must be >= 2")
        if price <= 0:
            raise ValueError("price must be positive")

        tau = horizon_seconds / float(num_intervals)
        sigma2 = self.volatility_sec**2

        # Discrete-time urgency parameter kappa
        # (2 / tau^2) * [ cosh(kappa * tau) - 1 ] = (lambda * sigma^2) / eta
        # cosh(kappa * tau) = 1 + 0.5 * (lambda * sigma^2 * tau^2) / eta
        arg = 1.0 + 0.5 * (self.risk_aversion * sigma2 * (tau**2)) / self.temporary_impact_eta
        # Clamp to avoid floating point issues if risk_aversion is 0
        if arg <= 1.0000000001:
            kappa = 0.0
        else:
            kappa = math.acosh(arg) / tau

        # Compute trajectory x_j = remaining shares
        times = [j * tau for j in range(num_intervals + 1)]
        holdings: List[float] = []

        if kappa < 1e-8:
            # Linear TWAP as lambda -> 0
            for t in times:
                holdings.append(total_quantity * max(0.0, 1.0 - (t / horizon_seconds)))
            half_life = horizon_seconds / 2.0
        else:
            sinh_kappa_T = math.sinh(kappa * horizon_seconds)
            for t in times:
                frac = math.sinh(kappa * (horizon_seconds - t)) / sinh_kappa_T
                holdings.append(total_quantity * max(0.0, min(1.0, frac)))
            half_life = math.log(2.0) / kappa

        holdings[0] = total_quantity
        holdings[-1] = 0.0

        # Child slices n_j = x_{j-1} - x_j
        slices = [holdings[j - 1] - holdings[j] for j in range(1, num_intervals + 1)]

        # Expected shortfall: E[x] = 0.5 * gamma * X^2 + (eta / tau) * sum(n_j^2)
        perm_cost = 0.5 * self.permanent_impact_gamma * (total_quantity**2)
        temp_cost = (self.temporary_impact_eta / tau) * sum(n**2 for n in slices)
        expected_shortfall = perm_cost + temp_cost
        notional = total_quantity * price
        expected_shortfall_bps = (expected_shortfall / notional) * 10_000.0 if notional > 0 else 0.0

        # Variance: V[x] = sigma^2 * sum_{j=1}^N tau * x_j^2
        variance = sigma2 * sum(tau * (holdings[j] ** 2) for j in range(1, num_intervals + 1))
        variance_bps_sq = (variance / (notional**2)) * (10_000.0**2) if notional > 0 else 0.0

        return AlmgrenChrissTrajectory(
            total_quantity=total_quantity,
            horizon_seconds=horizon_seconds,
            num_intervals=num_intervals,
            kappa=round(kappa, 6),
            half_life_seconds=round(half_life, 2),
            expected_shortfall_bps=round(expected_shortfall_bps, 4),
            variance_bps_sq=round(variance_bps_sq, 4),
            target_holdings=tuple(round(h, 4) for h in holdings),
            slice_quantities=tuple(round(s, 4) for s in slices),
            slice_times_sec=tuple(round(t, 2) for t in times),
        )

    def adapt_slice_realtime(
        self,
        base_slice_quantity: float,
        current_spread_bps: float,
        baseline_spread_bps: float,
        current_volume_rate: float,
        baseline_volume_rate: float,
        remaining_quantity: float,
        time_elapsed_pct: float,
    ) -> AdaptiveExecutionUpdate:
        """Adapt a child order size in response to real-time order book and liquidity dynamics.
        
        - If spread widens significantly (>1.5x baseline), decelerate slice to avoid paying wide spread.
        - If market volume rate surges (>1.2x baseline), accelerate slice to capitalize on liquidity.
        - As time elapses (>80%), urgency increases to ensure complete execution by horizon.
        """
        if base_slice_quantity <= 0:
            raise ValueError("base_slice_quantity must be positive")
        if current_spread_bps <= 0 or baseline_spread_bps <= 0:
            raise ValueError("spreads must be positive")
        if current_volume_rate <= 0 or baseline_volume_rate <= 0:
            raise ValueError("volume rates must be positive")

        spread_ratio = current_spread_bps / baseline_spread_bps
        vol_ratio = current_volume_rate / baseline_volume_rate

        # Spread penalty: if spread is wide, reduce size
        if spread_ratio > 1.2:
            spread_factor = max(0.5, 1.0 - 0.5 * (spread_ratio - 1.0))
            spread_reason = f"spread widened ({spread_ratio:.2f}x)"
        else:
            spread_factor = 1.0
            spread_reason = "spread normal"

        # Volume bonus: if volume is heavy, absorb liquidity
        if vol_ratio > 1.1:
            vol_factor = min(1.8, 1.0 + 0.5 * (vol_ratio - 1.0))
            vol_reason = f"volume surge ({vol_ratio:.2f}x)"
        else:
            vol_factor = max(0.6, vol_ratio)
            vol_reason = "volume modest"

        # Urgency ramp: as horizon approaches, finish order
        urgency = 1.0
        if time_elapsed_pct > 0.8:
            urgency = 1.0 + 2.0 * (time_elapsed_pct - 0.8)

        # Blended multiplier
        multiplier = spread_factor * vol_factor * urgency
        multiplier = max(0.3, min(2.5, multiplier))

        adapted = base_slice_quantity * multiplier
        adapted = min(adapted, remaining_quantity)

        reason = f"{spread_reason}; {vol_reason}; urgency={urgency:.2f}"

        return AdaptiveExecutionUpdate(
            original_target_slice=round(base_slice_quantity, 4),
            adapted_slice=round(adapted, 4),
            spread_penalty=round(1.0 - spread_factor, 4),
            volume_bonus=round(vol_factor - 1.0, 4),
            urgency_multiplier=round(urgency, 4),
            reason=reason,
        )


__all__ = [
    "AlmgrenChrissTrajectory",
    "AdaptiveExecutionUpdate",
    "AlmgrenChrissExecutionEngine",
]
