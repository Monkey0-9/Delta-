"""P2: label primitives embargo by default; no direct consumer can train
on the unknowable tail."""
from __future__ import annotations

import sys

import pandas as pd

sys.path.insert(0, ".")

from data.labels.engine import (build_label_frame, direction_labels,
                                drawdown_labels, future_returns,
                                future_volatility)


def _close(n: int = 60) -> pd.Series:
    import numpy as np

    idx = pd.date_range("2026-01-01", periods=n, freq="D", tz="UTC")
    # NOTE: pd.Series(values_series, index=idx) would reindex-align to NaN;
    # pass a raw ndarray so values actually land on the index.
    return pd.Series(100.0 + np.arange(n, dtype=float) * 0.5, index=idx)


def test_primitive_tails_are_unusable():
    close = _close()
    # House convention (shared with triple_barrier/build_label_frame):
    # rows cut+1.. are NA where cut = n-h-embargo, i.e. last h+e-1 rows.
    fr = future_returns(close)
    assert fr["future_return_20d"].iloc[-20:].isna().all()
    assert fr["future_return_5d"].iloc[-5:].isna().all()
    assert fr["future_return_1d"].iloc[-1:].isna().all()
    assert future_volatility(close).iloc[-5:].isna().all()
    assert direction_labels(close).iloc[-5:].isna().all()
    assert drawdown_labels(close).iloc[-20:].isna().all()
    # Heads still carry real labels.
    assert fr["future_return_5d"].iloc[0] > 0
    assert direction_labels(close).iloc[0] == 1


def test_explicit_zero_embargo_is_audited_opt_out():
    close = _close()
    fr = future_returns(close, embargo_bars=0)
    # Horizon tail still NaN (unknowable), embargo rows exposed by choice.
    assert fr["future_return_5d"].iloc[-5:].isna().all()
    assert not fr["future_return_5d"].iloc[-6:].isna().all()


def test_composite_frame_still_embargoed():
    frame = build_label_frame(_close())
    for col in ("future_return_1d", "future_return_5d", "future_return_20d",
                "future_volatility", "direction", "drawdown_20d",
                "triple_barrier"):
        assert pd.isna(frame[col].iloc[-1]), col


def test_ic_pvalue_is_real_inference():
    """P2: the IC p-value must separate signal from noise (fixed seed,
    deterministic) — the old |IC|-derived proxy could not."""
    import sys

    import numpy as np

    sys.path.insert(0, ".")
    from research.real_loop.validate import ic_permutation_pvalue

    rng = np.random.default_rng(0)
    n = 200
    fwd = pd.Series(rng.normal(size=n))
    signal_scores = pd.Series(fwd.to_numpy() + rng.normal(scale=0.5, size=n))
    noise_scores = pd.Series(rng.normal(size=n))
    p_signal = ic_permutation_pvalue(signal_scores, fwd)
    p_noise = ic_permutation_pvalue(noise_scores, fwd)
    assert p_signal < 0.05, p_signal
    assert p_noise > 0.05, p_noise
    assert ic_permutation_pvalue(signal_scores, fwd) == p_signal  # seeded
    assert ic_permutation_pvalue(
        pd.Series([1.0] * 5), pd.Series([1.0] * 5)) == 1.0  # too short
