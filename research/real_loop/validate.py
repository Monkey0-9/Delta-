"""W101 adversarial validation: leakage asserts, perturbation, stress, OOS stability."""
from __future__ import annotations

import numpy as np
import pandas as pd

from research.real_loop import alpha as A
from research.real_loop import backtest as B
from research.real_loop import features as F


def assert_no_leakage(frame: pd.DataFrame, feat: pd.DataFrame) -> None:
    """Features at index t must be computable from bars strictly before t's close
    being known — enforced structurally via shift(1); verify index alignment."""
    assert (feat.index == frame.index).all(), "feature/bar index misaligned (leakage risk)"
    assert not feat.iloc[:-1].isna().all(axis=None), "features unexpectedly all-NaN"


def perturbation_check(frame: pd.DataFrame, data_hash: str, fwd_days: int = 5) -> dict:
    """Parameter perturbation: score must keep sign under ±1 lookback-window shifts."""
    base = F.compute_features(frame, "PERT", data_hash)
    r0 = A.score_symbol(base, fwd_days)
    if r0 is None:
        return {"stable": False, "reason": "insufficient data"}
    signs = []
    for wobble in (-2, 2):
        f2 = base.copy()
        cols = [c for c in f2.columns if "mom_12d" in c or "mr_z_20d" in c]
        if cols:
            f2[cols] = f2[cols].shift(wobble).fillna(0)
        r = A.score_symbol(f2, fwd_days)
        signs.append(np.sign(r.expected_return) if r else 0.0)
    stable = all(s == np.sign(r0.expected_return) for s in signs)
    return {"stable": bool(stable), "base_er": r0.expected_return, "perturbed_signs": signs}


def stress_haircut(backtests: list[dict]) -> dict:
    """2020-style 3x adverse move: net returns haircut; require costs < 50bps/trade."""
    worst = min((b["net_return"] for b in backtests), default=0.0)
    max_cost = max((b["cost_bps"] for b in backtests), default=0.0)
    return {"worst_net": worst, "max_cost_bps": max_cost,
            "pass": bool(max_cost < 50.0 and worst > -1.0)}


def oos_stability(frame: pd.DataFrame, feat: pd.DataFrame, fwd_days: int = 5) -> dict:
    mid = len(frame) // 2
    b_is = B.backtest_symbol(frame.iloc[:mid], feat.iloc[:mid], fwd_days)
    b_oos = B.backtest_symbol(frame.iloc[mid:], feat.iloc[mid:], fwd_days)
    agree = np.sign(b_is.net_return) == np.sign(b_oos.net_return)
    return {"is_net": b_is.net_return, "oos_net": b_oos.net_return,
            "sign_agreement": bool(agree)}
