from __future__ import annotations

import numpy as np


def historical_var(
    returns,
    confidence: float = 0.95,
) -> float:

    values = np.asarray(
        returns,
        dtype=float,
    )

    if values.size < 20:
        raise ValueError(
            "minimum 20 observations required"
        )

    if not 0 < confidence < 1:
        raise ValueError(
            "confidence must be between 0 and 1"
        )

    return float(
        -np.quantile(
            values,
            1.0 - confidence,
        )
    )


def historical_cvar(
    returns,
    confidence: float = 0.95,
) -> float:

    values = np.asarray(
        returns,
        dtype=float,
    )

    threshold = np.quantile(
        values,
        1.0 - confidence,
    )

    tail = values[
        values <= threshold
    ]

    if len(tail) == 0:
        return historical_var(
            values,
            confidence,
        )

    return float(-tail.mean())


def risk_report(
    returns,
) -> dict:

    return {
        "VaR95":
            historical_var(
                returns,
                0.95,
            ),
        "CVaR95":
            historical_cvar(
                returns,
                0.95,
            ),
        "VaR99":
            historical_var(
                returns,
                0.99,
            ),
        "CVaR99":
            historical_cvar(
                returns,
                0.99,
            ),
    }