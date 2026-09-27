from __future__ import annotations

import numpy as np
import pandas as pd

from research.finalization.ablations import (
    matrix,
    validate_matrix,
)
from research.finalization.baselines import (
    run_baselines,
)
from research.finalization.statistics import (
    benjamini_hochberg,
    max_drawdown,
    metric_report,
    sharpe,
)
from research.finalization.stress import (
    stress_report,
)


def test_ablation_matrix() -> None:

    validate_matrix()

    experiments = matrix()

    assert len(experiments) == 7
    assert experiments[0]["experiment_id"] == (
        "W85_DELTA_STATIC"
    )


def test_sharpe_deterministic() -> None:

    returns = np.array(
        [
            0.01,
            -0.005,
            0.002,
            0.004,
            -0.003,
        ]
    )

    result = sharpe(
        returns
    )

    assert np.isfinite(result)


def test_drawdown() -> None:

    returns = np.array(
        [
            0.10,
            -0.20,
            0.05,
        ]
    )

    result = max_drawdown(
        returns
    )

    assert result < 0


def test_metric_report() -> None:

    returns = np.array(
        [
            0.01,
            0.02,
            -0.01,
            0.005,
            -0.003,
        ]
    )

    result = metric_report(
        "TEST",
        returns,
    )

    assert result.strategy == "TEST"
    assert result.observations == 5
    assert np.isfinite(
        result.sharpe
    )


def test_bh() -> None:

    result = benjamini_hochberg(
        [
            0.001,
            0.01,
            0.50,
            0.80,
        ]
    )

    assert len(result) == 4
    assert result[0] is True


def test_baselines() -> None:

    dates = pd.date_range(
        "2020-01-01",
        periods=100,
        freq="D",
        tz="UTC",
    )

    rows = []

    for asset, multiplier in [
        ("A", 1.0),
        ("B", 1.1),
        ("C", 0.9),
    ]:

        for i, date in enumerate(dates):

            rows.append(
                {
                    "date": date,
                    "asset": asset,
                    "close": (
                        100
                        * multiplier
                        * (1.0005 ** i)
                    ),
                }
            )

    prices = pd.DataFrame(
        rows
    )

    result = run_baselines(
        prices
    )

    assert not result.empty
    assert "momentum" in result.columns
    assert "mean_reversion" in result.columns
    assert "volatility_target" in result.columns


def test_stress() -> None:

    returns = np.array(
        [
            0.01,
            -0.02,
            0.005,
            -0.01,
            0.003,
        ]
    )

    result = stress_report(
        returns
    )

    assert len(result) == 5

    for row in result:
        assert row["survives"] is True
