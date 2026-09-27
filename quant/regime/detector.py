"""Regime detector: statistics -> Regime classification + transition matrix.

Reference Python implementation. Deterministic, fail-closed on empty input.
"""
from __future__ import annotations

from decimal import Decimal

from quant.regime.regime import Regime


def classify_regime(
    *,
    realized_vol: Decimal,
    vol_high_threshold: Decimal,
    trend_strength: Decimal,
    trend_threshold: Decimal = Decimal("0.5"),
    avg_correlation: Decimal = Decimal("0"),
    crisis_corr_threshold: Decimal = Decimal("0.7"),
    spread_bps: Decimal = Decimal("0"),
    spread_stress_bps: Decimal = Decimal("100"),
) -> Regime:
    """Priority: crisis > illiquid > high_volatility > trending > normal."""
    if realized_vol < 0:
        raise ValueError("realized_vol must be non-negative.")
    if vol_high_threshold <= 0:
        raise ValueError("vol_high_threshold must be positive.")
    if realized_vol >= vol_high_threshold and avg_correlation >= crisis_corr_threshold:
        return Regime.CRISIS
    if spread_bps >= spread_stress_bps:
        return Regime.ILLIQUID
    if realized_vol >= vol_high_threshold:
        return Regime.HIGH_VOLATILITY
    if abs(trend_strength) >= trend_threshold:
        return Regime.TRENDING
    return Regime.NORMAL


def transition_matrix(history: tuple[Regime, ...]) -> dict[tuple[str, str], Decimal]:
    """Empirical P(next | current) from a regime history. Empty -> {}."""
    if len(history) < 2:
        return {}
    counts: dict[tuple[str, str], int] = {}
    totals: dict[str, int] = {}
    for prev, nxt in zip(history, history[1:]):
        key = (prev.value, nxt.value)
        counts[key] = counts.get(key, 0) + 1
        totals[prev.value] = totals.get(prev.value, 0) + 1
    return {k: Decimal(v) / Decimal(totals[k[0]]) for k, v in counts.items()}


def regime_conditioned_weight(regime: Regime, base_weight: Decimal) -> Decimal:
    """Scale exposure by regime: crisis/illiquid -> 0, high_vol -> half."""
    if base_weight < 0:
        raise ValueError("base_weight must be non-negative.")
    scale = {
        Regime.CRISIS: Decimal("0"),
        Regime.ILLIQUID: Decimal("0"),
        Regime.HIGH_VOLATILITY: Decimal("0.5"),
        Regime.TRENDING: Decimal("1"),
        Regime.NORMAL: Decimal("1"),
    }[regime]
    return base_weight * scale


def cusum_change_points(values: tuple[float, ...], drift: float = 0.5, threshold: float = 5.0) -> tuple[int, ...]:
    """One-sided CUSUM change-point indices. Deterministic, fail-closed on input."""
    if drift <= 0 or threshold <= 0:
        raise ValueError("drift/threshold must be positive.")
    if len(values) < 3:
        return ()
    mean = sum(values) / len(values)
    points: list[int] = []
    pos = neg = 0.0
    for i, x in enumerate(values):
        pos = max(0.0, pos + (x - mean - drift))
        neg = min(0.0, neg + (x - mean + drift))
        if pos > threshold or -neg > threshold:
            points.append(i)
            pos = neg = 0.0
    return tuple(points)


def macro_regime(*, rate_change_bp: float, inflation_yoy: float, growth_yoy: float) -> Regime:
    """Rule-based macro overlay: tightening, stagflation risk, or normal."""
    if rate_change_bp > 100 and inflation_yoy > 0.05:
        return Regime.CRISIS
    if inflation_yoy > 0.05 and growth_yoy < 0.01:
        return Regime.HIGH_VOLATILITY
    if growth_yoy > 0.03 and inflation_yoy < 0.04:
        return Regime.TRENDING
    return Regime.NORMAL
