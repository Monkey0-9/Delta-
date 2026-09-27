from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class AssetRiskContribution:
    asset: str
    marginal_risk: float
    component_risk: float


def calculate(
    assets: list[str],
    weights,
    covariance,
) -> list[AssetRiskContribution]:

    w = np.asarray(
        weights,
        dtype=float,
    )

    sigma = np.asarray(
        covariance,
        dtype=float,
    )

    if sigma.shape != (
        len(w),
        len(w),
    ):
        raise ValueError(
            "covariance dimension mismatch"
        )

    portfolio_variance = float(
        w @ sigma @ w
    )

    if portfolio_variance <= 0:
        raise ValueError(
            "portfolio variance must be positive"
        )

    marginal = sigma @ w

    component = (
        w * marginal
        / portfolio_variance
    )

    return [
        AssetRiskContribution(
            asset=asset,
            marginal_risk=float(
                marginal[i]
            ),
            component_risk=float(
                component[i]
            ),
        )
        for i, asset in enumerate(assets)
    ]