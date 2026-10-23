"""Mathematical invariant unit tests for portfolio weight capping.

Verifies exact bounded simplex projection:
1. No weight exceeds max_weight.
2. Weights sum to 1.0 (within numerical tolerance).
3. Concentrated inputs do not re-inflate above max_weight upon normalization.
4. Infeasible constraints (n * max_weight < 1.0) raise an explicit ValueError.
"""
from __future__ import annotations

import numpy as np
import pytest

from research.real_loop.portfolio_risk import _cap


def test_cap_concentrated_two_assets():
    # Previous buggy behavior: [0.9, 0.1] with max_weight=0.6 produced [0.857, 0.143]
    # New bounded projection: produces exactly [0.6, 0.4]
    w = np.array([0.9, 0.1])
    res = _cap(w, 0.6)
    assert np.all(res <= 0.6 + 1e-12)
    assert np.all(res >= 0.0)
    assert np.isclose(res.sum(), 1.0)
    assert np.isclose(res[0], 0.6)
    assert np.isclose(res[1], 0.4)


def test_cap_multi_asset_cascade():
    # 5 assets with concentrated weights
    w = np.array([0.5, 0.3, 0.1, 0.05, 0.05])
    res = _cap(w, 0.25)
    assert np.all(res <= 0.25 + 1e-12)
    assert np.all(res >= 0.0)
    assert np.isclose(res.sum(), 1.0)
    # The first two assets should be clamped to 0.25
    assert np.isclose(res[0], 0.25)
    assert np.isclose(res[1], 0.25)


def test_cap_already_compliant():
    w = np.array([0.2, 0.2, 0.2, 0.2, 0.2])
    res = _cap(w, 0.25)
    assert np.allclose(res, 0.2)
    assert np.isclose(res.sum(), 1.0)


def test_cap_infeasible_raises_value_error():
    # 2 assets with max_weight 0.4 can only sum to 0.8 < 1.0 -> infeasible!
    w = np.array([0.5, 0.5])
    with pytest.raises(ValueError, match="Infeasible weight cap"):
        _cap(w, 0.4)


def test_cap_empty_and_zero_inputs():
    res_empty = _cap(np.array([]), 0.5)
    assert len(res_empty) == 0

    res_zeros = _cap(np.array([0.0, 0.0, 0.0, 0.0]), 0.5)
    assert np.allclose(res_zeros, 0.25)
    assert np.isclose(res_zeros.sum(), 1.0)
