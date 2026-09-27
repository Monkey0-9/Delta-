from __future__ import annotations

from decimal import Decimal


def cross_sectional_rank(values: dict[str, Decimal]) -> dict[str, Decimal]:
    """Rank factor values into [0,1] quantiles (1 = highest)."""
    ordered = sorted(values, key=lambda k: values[k])
    n = len(ordered)
    if n < 2:
        return {k: Decimal("0.5") for k in values}
    return {k: Decimal(str(i / (n - 1))) for i, k in enumerate(ordered)}
