"""Stage-1 label engine (plan F): PIT-aligned, embargo-aware, triple-barrier.

Only leakage guards existed before (data/pit/leakage.py). This module builds
future_return_1d/5d/20d, future_volatility, direction, drawdown, tail_loss,
risk_adjusted_return, event labels, and triple-barrier labels — all PIT-aligned
with overlap/embargo handling. Future-label fixtures must FAIL leakage tests.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import numpy as np
import pandas as pd


class LabelKind(str, Enum):
    FUTURE_RETURN_1D = "future_return_1d"
    FUTURE_RETURN_5D = "future_return_5d"
    FUTURE_RETURN_20D = "future_return_20d"
    FUTURE_VOL = "future_volatility"
    DIRECTION = "direction"
    DRAWDOWN = "drawdown"
    TAIL_LOSS = "tail_loss"
    RISK_ADJ = "risk_adjusted_return"
    TRIPLE_BARRIER = "triple_barrier"


@dataclass(frozen=True, slots=True)
class LabelSpec:
    kind: LabelKind
    horizon: int = 5
    embargo_bars: int = 1
    pt_mult: float = 1.0
    sl_mult: float = 1.0
    vol_lookback: int = 20


def _embargo_cut(n: int, horizon: int, embargo: int) -> int:
    return max(0, n - horizon - embargo)


def future_returns(close: pd.Series, horizons: tuple[int, ...] = (1, 5, 20),
                   embargo_bars: int = 1) -> pd.DataFrame:
    """Forward returns per horizon. P2: each column's last h+embargo rows are
    NaN — the horizon extends past available data there, so no consumer can
    train or evaluate on unknowable labels. Pass embargo_bars=0 only when the
    caller enforces purge/embargo itself (documented, audited)."""
    out = pd.DataFrame(index=close.index)
    n = len(close)
    for h in horizons:
        col = close.shift(-h) / close - 1.0
        cut = _embargo_cut(n, h, embargo_bars)
        col.iloc[cut + 1:] = np.nan
        out[f"future_return_{h}d"] = col
    return out


def future_volatility(close: pd.Series, horizon: int = 5,
                      embargo_bars: int = 1) -> pd.Series:
    rets = np.log(close / close.shift(1))
    out = rets.shift(-horizon).rolling(horizon).std() * np.sqrt(252.0)
    out.iloc[_embargo_cut(len(close), horizon, embargo_bars) + 1:] = np.nan
    return out


def direction_labels(close: pd.Series, horizon: int = 5,
                     embargo_bars: int = 1) -> pd.Series:
    fr = close.shift(-horizon) / close - 1.0
    out = fr.apply(lambda x: 1 if x > 0 else (-1 if x < 0 else 0)).astype("Int64")
    out.iloc[_embargo_cut(len(close), horizon, embargo_bars) + 1:] = pd.NA
    return out


def drawdown_labels(close: pd.Series, horizon: int = 20,
                    embargo_bars: int = 1) -> pd.Series:
    out = pd.Series(np.nan, index=close.index, dtype=float)
    vals = close.to_numpy()
    # P2: stop embargo rows early — the window would run past usable data.
    for i in range(_embargo_cut(len(vals), horizon, embargo_bars) + 1):
        window = vals[i + 1: i + 1 + horizon]
        peak = np.maximum.accumulate(np.concatenate([[vals[i]], window]))
        dd = (window / peak[1:] - 1.0).min()
        out.iloc[i] = dd
    return out


def triple_barrier(close: pd.Series, spec: LabelSpec) -> pd.Series:
    rets = np.log(close / close.shift(1))
    vol = rets.rolling(spec.vol_lookback).std().bfill()
    out = pd.Series(0, index=close.index, dtype="Int64")
    px = close.to_numpy()
    vv = vol.to_numpy()
    n = len(px)
    for i in range(n - 1):
        upper = px[i] * (1.0 + spec.pt_mult * vv[i])
        lower = px[i] * (1.0 - spec.sl_mult * vv[i])
        label = 0
        for j in range(i + 1, min(i + 1 + spec.horizon, n)):
            if px[j] >= upper:
                label = 1
                break
            if px[j] <= lower:
                label = -1
                break
        out.iloc[i] = label
    out.iloc[_embargo_cut(n, spec.horizon, spec.embargo_bars) + 1:] = pd.NA
    return out.astype("Int64")


def build_label_frame(close: pd.Series, embargo_bars: int = 1) -> pd.DataFrame:
    frame = pd.DataFrame(index=close.index)
    frame = frame.join(future_returns(close))
    frame["future_volatility"] = future_volatility(close).to_numpy()
    frame["direction"] = direction_labels(close).to_numpy()
    frame["drawdown_20d"] = drawdown_labels(close).to_numpy()
    tb = triple_barrier(close, LabelSpec(kind=LabelKind.TRIPLE_BARRIER))
    frame["triple_barrier"] = tb.to_numpy()
    n = len(frame)
    cut = _embargo_cut(n, 20, embargo_bars)
    frame.iloc[cut + 1:, frame.columns.get_loc("future_return_20d")] = np.nan
    cut5 = _embargo_cut(n, 5, embargo_bars)
    for c in ("future_return_5d", "future_volatility", "direction", "triple_barrier"):
        frame.iloc[cut5 + 1:, frame.columns.get_loc(c)] = pd.NA if c in ("direction", "triple_barrier") else np.nan
    frame.iloc[_embargo_cut(n, 1, embargo_bars) + 1:, frame.columns.get_loc("future_return_1d")] = np.nan
    return frame


__all__ = ["LabelKind", "LabelSpec", "future_returns", "future_volatility",
           "direction_labels", "drawdown_labels", "triple_barrier", "build_label_frame"]
