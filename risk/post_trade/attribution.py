from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class AttributionLine:
    segment: str
    allocation: Decimal
    selection: Decimal
    total: Decimal


@dataclass(frozen=True, slots=True)
class AttributionReport:
    lines: tuple[AttributionLine, ...]
    total: Decimal


def brinson_attribution(
    *,
    portfolio_weights: dict[str, Decimal],
    benchmark_weights: dict[str, Decimal],
    portfolio_returns: dict[str, Decimal],
    benchmark_returns: dict[str, Decimal],
) -> AttributionReport:
    """Brinson-Hood-Beebower allocation/selection attribution.

    Allocation = (wp - wb) * rb; Selection = wp * (rp - rb).
    Fail-closed on misaligned segments.
    """
    if (
        set(portfolio_weights) != set(benchmark_weights)
        or set(portfolio_weights) != set(portfolio_returns)
        or set(portfolio_weights) != set(benchmark_returns)
    ):
        raise ValueError("segments must align.")
    lines: list[AttributionLine] = []
    for seg in sorted(portfolio_weights):
        alloc = (portfolio_weights[seg] - benchmark_weights[seg]) * benchmark_returns[seg]
        sel = portfolio_weights[seg] * (portfolio_returns[seg] - benchmark_returns[seg])
        lines.append(AttributionLine(seg, alloc, sel, alloc + sel))
    total = sum((ln.total for ln in lines), Decimal("0"))
    return AttributionReport(tuple(lines), total)


def factor_attribution(
    exposures: dict[str, Decimal], factor_returns: dict[str, Decimal]
) -> dict[str, Decimal]:
    """PnL per factor = exposure * factor return. Fail-closed on mismatch."""
    if set(exposures) != set(factor_returns):
        raise ValueError("exposures/factor_returns must align.")
    return {k: exposures[k] * factor_returns[k] for k in sorted(exposures)}
