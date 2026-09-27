from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class ChildOrder:
    slice_id: int
    quantity: float
    weight: float
    urgency: float


def twap(
    quantity: float,
    slices: int,
) -> list[ChildOrder]:

    if quantity <= 0:
        raise ValueError(
            "quantity must be positive"
        )

    if slices <= 0:
        raise ValueError(
            "slices must be positive"
        )

    child = quantity / slices

    return [
        ChildOrder(
            slice_id=i,
            quantity=child,
            weight=1.0 / slices,
            urgency=0.0,
        )
        for i in range(slices)
    ]


def vwap(
    quantity: float,
    expected_volume,
) -> list[ChildOrder]:

    volume = np.asarray(
        expected_volume,
        dtype=float,
    )

    if len(volume) == 0:
        raise ValueError(
            "volume curve cannot be empty"
        )

    if np.any(volume < 0):
        raise ValueError(
            "volume cannot be negative"
        )

    total = volume.sum()

    if total <= 0:
        return twap(
            quantity,
            len(volume),
        )

    weights = volume / total

    return [
        ChildOrder(
            slice_id=i,
            quantity=float(
                quantity * weight
            ),
            weight=float(weight),
            urgency=0.0,
        )
        for i, weight in enumerate(weights)
    ]


def pov(
    quantity: float,
    market_volume,
    participation: float = 0.10,
) -> list[ChildOrder]:

    if not 0 < participation <= 1:
        raise ValueError(
            "participation must be in (0,1]"
        )

    volume = np.asarray(
        market_volume,
        dtype=float,
    )

    remaining = quantity
    result = []

    for i, market_slice in enumerate(
        volume
    ):
        if remaining <= 0:
            break

        child = min(
            remaining,
            market_slice * participation,
        )

        result.append(
            ChildOrder(
                slice_id=i,
                quantity=float(child),
                weight=(
                    float(child / quantity)
                ),
                urgency=0.0,
            )
        )

        remaining -= child

    if remaining > 0:
        result.append(
            ChildOrder(
                slice_id=len(result),
                quantity=float(remaining),
                weight=float(
                    remaining / quantity
                ),
                urgency=1.0,
            )
        )

    return result


def implementation_shortfall(
    quantity: float,
    arrival_price: float,
    candidate_prices,
    risk_aversion: float = 0.5,
) -> list[ChildOrder]:

    prices = np.asarray(
        candidate_prices,
        dtype=float,
    )

    deviation = np.abs(
        prices - arrival_price
    )

    urgency = np.exp(
        -risk_aversion * deviation
    )

    weights = (
        urgency
        / urgency.sum()
    )

    return [
        ChildOrder(
            slice_id=i,
            quantity=float(
                quantity * weight
            ),
            weight=float(weight),
            urgency=float(weight),
        )
        for i, weight in enumerate(weights)
    ]