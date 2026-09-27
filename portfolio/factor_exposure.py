"""Factor exposure: portfolio weights x factor loadings -> factor bets."""
from __future__ import annotations

from decimal import Decimal
from typing import Mapping


def factor_exposure(
    weights: Mapping[str, Decimal],
    loadings: Mapping[str, Mapping[str, Decimal]],
) -> dict[str, Decimal]:
    """Sum over assets of weight * loading per factor. Fail-closed on unknown asset."""
    exposures: dict[str, Decimal] = {}
    for asset, weight in weights.items():
        if asset not in loadings:
            raise ValueError(f"missing loadings for asset: {asset}")
        for factor, loading in loadings[asset].items():
            exposures[factor] = exposures.get(factor, Decimal("0")) + weight * loading
    return exposures


def net_factor_exposure(exposures: Mapping[str, Decimal]) -> Decimal:
    """L1 norm of factor bets — 0 means factor-neutral."""
    return sum((abs(v) for v in exposures.values()), Decimal("0"))
