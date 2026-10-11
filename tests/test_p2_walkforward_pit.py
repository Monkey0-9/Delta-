"""P2/C: as_of truncation + per-fold PIT walk-forward."""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, ".")

from research.real_loop import features as F
from research.real_loop.walkforward import purged_splits, walk_forward_pit


def _frame(n: int = 300, seed: int = 9):
    idx = pd.date_range("2024-01-01", periods=n, freq="D", tz="UTC")
    rng = np.random.default_rng(seed)
    close = pd.Series(100 * np.cumprod(1 + rng.normal(0.0005, 0.01, n)),
                       index=idx)
    return pd.DataFrame(
        {"open": close, "high": close * 1.005, "low": close * 0.995,
         "close": close, "volume": 2_000_000}, index=idx)


def test_as_of_truncation_blocks_future_bars():
    frame = _frame()
    as_of = frame.index[199]
    feat = F.compute_features(frame, "PIT", "h-pit", as_of=as_of)
    assert (feat.index <= as_of).all()
    assert len(feat) == 200
    with pytest.raises(ValueError):
        F.compute_features(frame, "PIT", "h-pit",
                           as_of=as_of.tz_localize(None))


def test_fold_features_immune_to_post_train_bars():
    """The PIT guarantee: extending the frame past train-end cannot change
    already-computed fold features when as_of is fixed."""
    frame = _frame()
    as_of = frame.index[199]
    f_trunc = F.compute_features(frame.iloc[:250], "PIT2", "h-pit2",
                                 as_of=as_of)
    f_full = F.compute_features(frame, "PIT2", "h-pit2b", as_of=as_of)
    pd.testing.assert_frame_equal(f_trunc, f_full)


def test_walk_forward_pit_structure_and_determinism():
    frame = _frame()
    px = frame["close"]
    out1 = walk_forward_pit(px, frame, "PIT", "h-wf", n_folds=3)
    out2 = walk_forward_pit(px, frame, "PIT", "h-wf", n_folds=3)
    assert out1["version"] == "wf-v2-pit"
    assert out1 == out2  # deterministic
    assert out1["n_folds"] == len(
        purged_splits(len(px), 3, 5)), "same feasible folds as legacy"
    assert set(out1["gate"]) == {"pass", "rule"}
    for fold in out1["folds"]:
        assert set(fold) == {"n", "gross", "net", "hit", "sharpe"}
