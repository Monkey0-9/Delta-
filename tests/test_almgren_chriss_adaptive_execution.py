"""Test suite for Almgren-Chriss Optimal Execution Engine."""
import pytest
from execution.algorithms import (
    AdaptiveExecutionUpdate,
    AlmgrenChrissExecutionEngine,
    AlmgrenChrissTrajectory,
)


def test_almgren_chriss_twap_limit_at_zero_risk_aversion():
    # As lambda -> 0, trajectory must converge to linear TWAP
    engine = AlmgrenChrissExecutionEngine(risk_aversion=0.0)
    traj = engine.compute_trajectory(
        total_quantity=1000.0,
        horizon_seconds=600.0,
        num_intervals=5,
    )

    # 5 intervals means 200 shares each
    for s in traj.slice_quantities:
        assert abs(s - 200.0) < 1.0
    assert traj.kappa == 0.0
    assert abs(sum(traj.slice_quantities) - 1000.0) < 1e-4


def test_almgren_chriss_front_loading_under_high_risk_aversion():
    # With positive risk aversion, execution front-loads to mitigate volatility risk
    engine = AlmgrenChrissExecutionEngine(risk_aversion=1e-4, volatility_annual=0.40)
    traj = engine.compute_trajectory(
        total_quantity=1000.0,
        horizon_seconds=600.0,
        num_intervals=5,
    )

    assert traj.kappa > 0.0
    # First slice must be strictly larger than the last slice
    assert traj.slice_quantities[0] > traj.slice_quantities[-1]
    # Total executed shares must strictly match total_quantity
    assert abs(sum(traj.slice_quantities) - 1000.0) < 1e-4


def test_adaptive_execution_spread_and_volume_reaction():
    engine = AlmgrenChrissExecutionEngine()

    # Scenario A: Wide spread (2x baseline) -> should penalize/reduce slice
    up_wide = engine.adapt_slice_realtime(
        base_slice_quantity=100.0,
        current_spread_bps=10.0,
        baseline_spread_bps=5.0,
        current_volume_rate=1000.0,
        baseline_volume_rate=1000.0,
        remaining_quantity=500.0,
        time_elapsed_pct=0.2,
    )
    assert up_wide.adapted_slice < 100.0
    assert up_wide.spread_penalty > 0.0

    # Scenario B: Heavy volume surge (2x baseline) and tight spread -> should increase slice
    up_vol = engine.adapt_slice_realtime(
        base_slice_quantity=100.0,
        current_spread_bps=5.0,
        baseline_spread_bps=5.0,
        current_volume_rate=2000.0,
        baseline_volume_rate=1000.0,
        remaining_quantity=500.0,
        time_elapsed_pct=0.2,
    )
    assert up_vol.adapted_slice > 100.0
    assert up_vol.volume_bonus > 0.0


def test_error_validation():
    with pytest.raises(ValueError, match="total_quantity must be positive"):
        AlmgrenChrissExecutionEngine().compute_trajectory(0.0, 100.0)

    with pytest.raises(ValueError, match="num_intervals must be >= 2"):
        AlmgrenChrissExecutionEngine().compute_trajectory(100.0, 100.0, num_intervals=1)
