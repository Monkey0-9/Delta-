from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class StressScenario:
    name: str
    return_multiplier: float
    volatility_multiplier: float
    description: str


SCENARIOS = (
    StressScenario(
        "EQUITY_CRASH",
        -2.0,
        2.5,
        "Large negative return shock.",
    ),
    StressScenario(
        "VOLATILITY_SPIKE",
        0.5,
        3.0,
        "Volatility expansion.",
    ),
    StressScenario(
        "LIQUIDITY_SHOCK",
        1.0,
        2.0,
        "Execution uncertainty and wider costs.",
    ),
    StressScenario(
        "CORRELATION_CONVERGENCE",
        1.0,
        2.0,
        "Diversification benefit collapses.",
    ),
    StressScenario(
        "RATE_SHOCK",
        -1.5,
        1.8,
        "Large rate-sensitive asset shock.",
    ),
)


def apply_stress(
    returns: np.ndarray,
    scenario: StressScenario,
    seed: int = 42,
) -> np.ndarray:

    rng = np.random.default_rng(seed)

    noise = rng.normal(
        0.0,
        np.std(returns)
        * (
            scenario.volatility_multiplier
            - 1.0
        ),
        len(returns),
    )

    shocked = (
        returns
        * scenario.return_multiplier
        + noise
    )

    return shocked


def stress_report(
    returns: np.ndarray,
) -> list[dict]:

    output = []

    for scenario in SCENARIOS:

        stressed = apply_stress(
            returns,
            scenario,
        )

        equity = np.cumprod(
            1 + stressed
        )

        peak = np.maximum.accumulate(
            equity
        )

        dd = (
            equity / peak - 1
        ).min()

        output.append(
            {
                "scenario": scenario.name,
                "description": scenario.description,
                "mean_return": float(
                    stressed.mean()
                ),
                "worst_return": float(
                    stressed.min()
                ),
                "max_drawdown": float(dd),
                "survives": bool(
                    np.all(
                        np.isfinite(
                            stressed
                        )
                    )
                ),
            }
        )

    return output
