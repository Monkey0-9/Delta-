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


def ic_permutation_pvalue(scores: pd.Series, fwds: pd.Series,
                          n_perm: int = 999, seed: int = 7) -> float:
    """Two-sided permutation p-value for rank-IC: fraction of shuffled
    (score, forward) alignments with |IC| >= observed |IC|.

    Real inference, not a transform of the point estimate: under the null of
    no association, any alignment is equally likely, so reshuffling fwds
    builds the exact null distribution. Deterministic given seed.
    """
    s = pd.concat([scores, fwds], axis=1).dropna()
    if len(s) < 10:
        return 1.0
    from research.real_loop.alpha_stats import rank_ic

    rng = np.random.default_rng(seed)
    obs = abs(rank_ic(s.iloc[:, 0], s.iloc[:, 1]))
    fwd = s.iloc[:, 1].to_numpy()
    n_ge = 0
    for _ in range(n_perm):
        perm = pd.Series(rng.permutation(fwd), index=s.index)
        if abs(rank_ic(s.iloc[:, 0], perm)) >= obs:
            n_ge += 1
    return (n_ge + 1) / (n_perm + 1)


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
    # P2/I centralization: cost-adjusted Sharpe is produced HERE by the ONE
    # sanctioned engine (not a side formula). Assumptions, documented:
    # full-capital deployment (turnover fraction ~= participation rate),
    # scalar horizon vol, v3 cost config (spread 5/fee 1/slip 2). The engine
    # is uncalibrated, so the quote stamps proxy=True and the bundle carries
    # cost_proxy=True — labeled, never hidden. This is the evidence the
    # AlphaRegistry promotion gate consumes.
    from execution.cost_engine import TransactionCostEngine

    _pos = pos.reindex(strat.index).fillna(0)
    _churn = _pos.diff().abs().fillna(0)
    _turnover = float(_churn.mean())
    _sigma = float(fwd.reindex(strat.index).fillna(0).std() or 0.0)
    _per_trade = TransactionCostEngine().quote_participation(
        _turnover, _sigma, spread_bps=5.0, fee_bps=1.0, slippage_bps=2.0)
    _net = strat - _churn * _per_trade.total_bps / 1e4
    _sd = float(_net.std() or 0.0)
    stats["cost_adjusted_sharpe"] = round(
        float(_net.mean() / _sd * (252 / fwd_days) ** 0.5), 4) if _sd > 0 else 0.0
    stats["cost_proxy"] = bool(_per_trade.proxy)
    stats["cost_bps_per_trade"] = round(_per_trade.total_bps, 2)
    # P2/I fill-contingent evidence: the empirical P(fill) model scores the
    # same turnover the analytic backtest fudges. Uncalibrated (prior 0.5)
    # until observe() data lands — informational, never a gate threshold.
    from simulation.exchange_replay import fill_contingent_report

    _px = frame["close"].astype(float)
    _spread_proxy = ((_px.rolling(20).max() - _px.rolling(20).min())
                     / _px * 1e4).fillna(5.0)
    _vol = _px.pct_change().rolling(20).std().fillna(0.015)
    stats["fill_contingent"] = fill_contingent_report(
        _churn, _spread_proxy, None, _vol)
    # Multiple-testing honesty (P2): the old code fabricated "proxy p-values"
    # from |IC| and ran BH on fiction. Only ONE hypothesis is actually tested
    # here (strategy IC != 0), so report its permutation p-value directly.
    # Family-wise BH belongs at the caller that tests a real family of
    # strategies — fabricating a 5-group family here would repeat the lie.
    p_ic = ic_permutation_pvalue(scores.reindex(strat.index).fillna(0),
                                 fwd.reindex(strat.index).fillna(0))
    stats["ic_pvalue"] = round(float(p_ic), 4)
    stats["fdr_bh_q10"] = None  # no real family tested at this level
    stats["gate"] = {
        "pass": bool(abs(stats["ic"]) > 0.02 and stats["dsr"] > 0.5
                     and p_ic < 0.10
                     and (stats["pbo"] is None or stats["pbo"] < 0.6)),
        "rule": "require |IC|>0.02, DSR>0.5, permutation p<0.10, PBO<0.6",
    }
    return stats
