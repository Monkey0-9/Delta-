from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class BarSlice:
    day: str
    volume: Decimal
    vwap: Decimal


@dataclass(frozen=True, slots=True)
class ExecutionSchedule:
    slices: tuple[Decimal, ...]
    benchmark: str  # TWAP | VWAP | POV | IS


def twap_schedule(total: Decimal, n: int) -> ExecutionSchedule:
    from execution.algorithms.slicing import twap_slices

    return ExecutionSchedule(twap_slices(total, n), "TWAP")


def vwap_schedule(total: Decimal, bars: tuple[BarSlice, ...]) -> ExecutionSchedule:
    from execution.algorithms.slicing import vwap_slices

    vols = tuple(b.volume for b in bars)
    return ExecutionSchedule(vwap_slices(total, vols), "VWAP")


def pov_schedule(
    total: Decimal, volumes: tuple[Decimal, ...], pov: Decimal
) -> ExecutionSchedule:
    """POV schedule capped so cumulative fills never exceed total."""
    from execution.algorithms.slicing import pov_slices

    raw = pov_slices(total, volumes, pov)
    capped: list[Decimal] = []
    filled = Decimal("0")
    for q in raw:
        q = min(q, total - filled)
        capped.append(q)
        filled += q
    return ExecutionSchedule(tuple(capped), "POV")


def is_schedule(
    total: Decimal,
    n: int,
    *,
    risk_aversion: Decimal = Decimal("0.5"),
    volatility: Decimal = Decimal("0.02"),
) -> ExecutionSchedule:
    """Almgren-Chriss-style IS schedule: front-loaded when urgency is high.

    Closed-form approximation: slice weights ∝ cosh(k*(T-t)); k rises with
    risk_aversion * volatility. Deterministic, sums exactly to total.
    """
    if n <= 0 or total <= 0:
        raise ValueError("total/n must be positive.")
    import math

    k = float(risk_aversion) * float(volatility) * 10.0
    weights = [math.cosh(k * (n - i) / n) for i in range(n)]
    tot = sum(weights) or 1.0
    slices = tuple(total * Decimal(str(w / tot)) for w in weights)
    dust = total - sum(slices)
    lst = list(slices)
    lst[-1] += dust
    return ExecutionSchedule(tuple(lst), "IS")


def arrival_price(
    slices: tuple[Decimal, ...],
    prices: tuple[Decimal, ...],
    arrival: Decimal,
    side: str = "BUY",
) -> Decimal:
    """Implementation shortfall vs arrival price (positive = cost)."""
    if len(slices) != len(prices) or not slices:
        raise ValueError("slices/prices must align and be non-empty.")
    if side not in ("BUY", "SELL"):
        raise ValueError("side must be BUY or SELL.")
    total = sum(slices)
    if total <= 0:
        raise ValueError("total must be positive.")
    vwap = sum(q * p for q, p in zip(slices, prices)) / total
    return (vwap - arrival) if side == "BUY" else (arrival - vwap)
