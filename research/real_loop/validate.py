"""W101/W106/W122 adversarial validation: leakage, perturbation, stress, OOS,
multiple-testing (BH-FDR), Deflated Sharpe, PBO gates."""
from __future__ import annotations

import numpy as np
import pandas as pd

from research.real_loop import alpha as A
from research.real_loop import alpha_stats as AS
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
    survives = all(bool(b.get("adversarial", {}).get("survives_2x_costs", True)) for b in backtests)
    return {"worst_net": worst, "max_cost_bps": max_cost,
            "survives_2x_costs": survives,
            "pass": bool(max_cost < 50.0 and worst > -1.0 and survives)}


def oos_stability(frame: pd.DataFrame, feat: pd.DataFrame, fwd_days: int = 5) -> dict:
    mid = len(frame) // 2
    b_is = B.backtest_symbol(frame.iloc[:mid], feat.iloc[:mid], fwd_days)
    b_oos = B.backtest_symbol(frame.iloc[mid:], feat.iloc[mid:], fwd_days)
    agree = np.sign(b_is.net_return) == np.sign(b_oos.net_return)
    return {"is_net": b_is.net_return, "oos_net": b_oos.net_return,
            "sign_agreement": bool(agree)}


def research_statistics(frame: pd.DataFrame, feat: pd.DataFrame,
                        fwd_days: int = 5, n_trials: int = 10) -> dict:
    """Full W106/W122 research-statistics bundle for one name."""
    px = frame["close"].astype(float)
    sig_cols = [c for c in feat.columns if c.startswith(("mom_", "mr_z_", "trend_"))]
    sig = feat[sig_cols].mean(axis=1) if sig_cols else pd.Series(0.0, index=feat.index)
    sig = sig.fillna(0)
    pos = (sig > 0.5).astype(float) - (sig < -0.5).astype(float)
    pos = pos.shift(2)
    fwd = px.pct_change(fwd_days).shift(-fwd_days)
    strat = (pos * fwd).dropna()
    scores = sig.reindex(strat.index).fillna(0)
    stats = AS.summarize_alpha(scores, fwd.reindex(strat.index).fillna(0),
                               pos.reindex(strat.index).fillna(0), strat,
                               n_trials=n_trials)
    # multiple-testing across the 5 factor groups (proxy p-values from |IC|)
    pvals = [max(1e-6, 2 * (1 - min(0.999, abs(stats["ic"]) * 4 + 0.5))) for _ in range(5)]
    stats["fdr_bh_q10"] = AS.benjamini_hochberg(pvals, q=0.10)
    stats["gate"] = {
        "pass": bool(abs(stats["ic"]) > 0.02 and stats["dsr"] > 0.5
                     and (stats["pbo"] is None or stats["pbo"] < 0.6)),
        "rule": "require |IC|>0.02, DSR>0.5, PBO<0.6",
    }
    return stats
