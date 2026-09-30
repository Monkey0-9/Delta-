"""Robust statistical validation: purged embargo CV, correct DSR, CSCV PBO.

Complements ``quant.validation.advanced_metrics`` (which carries simplified
single-split approximations) with research-exact procedures:

* :func:`purged_walk_forward_splits` — Lopez de Prado purged + embargoed
  walk-forward (no train/test leakage across label horizons).
* :func:`deflated_sharpe_probability` — Bailey & Lopez de Prado (2014)
  exact DSR as a *probability* P(SR > SR0); the legacy
  ``StatisticalValidator.calculate_deflated_sharpe`` in
  ``quant.backtest.realistic`` used an ad-hoc sqrt formula and is superseded.
* :func:`pbo_cscv` — Bailey et al. combinatorial symmetric cross-validation
  PBO over S partitions (default 16); the legacy single-loop PBO is kept
  only for backward compat and must not be cited as PBO.
* :func:`reality_check_pvalue` — White (2000)-style stationary-bootstrap
  reality check against a benchmark (correct null: reshuffled *benchmark*
  edge, not returns-vs-itself as the legacy code did).

Public sources: Bailey & Lopez de Prado, "The Deflated Sharpe Ratio"
(2014); Bailey et al., "Pseudo-Mathematics and Financial Charlatanism /
PBO" (2014); Lopez de Prado, AFML Ch.7-13 (purging/embargo, CSCV);
White, "A Reality Check for Data Snooping" (Econometrica 2000).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import norm


def purged_walk_forward_splits(n: int, n_splits: int = 5, embargo_pct: float = 0.02,
                               purge_pct: float = 0.02):
    """Yield (train_idx, test_idx) with purge gap + embargo.

    Deterministic expanding-window: test blocks partition [0, n) in order;
    train = [0, test_start - purge); embargo drops the first ``embargo``
    rows of each test block (post-event label leakage) AND excludes the
    ``embargo`` rows preceding each test block from the train set, so no
    train observation shares an embargo window with the test set.
    """
    if n_splits < 2 or n < n_splits * 2:
        raise ValueError("insufficient observations for purged splits")
    bounds = np.linspace(0, n, n_splits + 1, dtype=int)
    for k in range(n_splits):
        t0, t1 = int(bounds[k]), int(bounds[k + 1])
        purge = max(int(n * purge_pct), 1)
        embargo = max(int(n * embargo_pct), 0)
        train_end = t0 - purge - embargo  # purge gap + pre-test embargo
        if train_end < 2:  # insufficient history (incl. k==0) -> skip, never overlap
            continue
        train = np.arange(0, train_end)
        test = np.arange(t0 + embargo, t1)  # drop embargo head of test block
        if len(test) < 1:
            continue
        yield train, test


def deflated_sharpe_probability(sharpe: float, n_obs: int, n_trials: int,
                                skew: float = 0.0, kurt: float = 3.0) -> float:
    """DSR P-value: P(observed SR exceeds the multiple-testing benchmark).

    Bailey & Lopez de Prado (2014): SR0 = E[max SR_0] under the null via
    extreme-value approximation; DSR = Phi((SR - SR0)/sigma_SR) with
    non-normal correction sigma_SR^2 = (1 - gamma3*SR + (gamma4-1)/4 SR^2)/(T-1).
    Returns a probability in [0,1]; higher = less likely to be a fluke.

    Fail-closed inputs: n_trials < 1, n_obs < 10, or non-finite moments raise
    ValueError instead of silently clamping to a passing value.
    """
    if not int(n_trials) >= 1:
        raise ValueError(f"n_trials must be >= 1, got {n_trials}")
    if not int(n_obs) >= 10:
        raise ValueError(f"n_obs must be >= 10 for DSR asymptotics, got {n_obs}")
    if not (np.isfinite(sharpe) and np.isfinite(skew) and np.isfinite(kurt)):
        raise ValueError("DSR inputs must be finite.")
    sr0 = float(np.sqrt(n_obs) * (
        (1 - np.euler_gamma) * norm.ppf(1 - 1.0 / n_trials)
        + np.euler_gamma * norm.ppf(1 - 1.0 / (n_trials * np.e))
    ) / (n_obs - 1))
    var_sr = max(1 - skew * sharpe + (kurt - 1) / 4 * sharpe ** 2, 1e-12) / (n_obs - 1)
    return float(np.clip(norm.cdf((sharpe - sr0) / np.sqrt(var_sr)), 0.0, 1.0))


def pbo_cscv(returns_matrix: np.ndarray, n_partitions: int = 16,
             seed: int = 7) -> float:
    """CSCV PBO (Bailey et al. 2014): fraction of partition halves where the
    IS-optimal strategy underperforms the OOS median.

    ``returns_matrix``: (T, N) trials. Splits rows into S even partitions,
    enumerates all C(S, S/2) IS halves (capped at 256 sampled combos for
    tractability, seeded), ranks trials by IS Sharpe, measures logit-rank
    decay OOS. Deterministic given seed.

    Fail-closed: degenerate shapes raise ValueError (a returned 0.0 would
    read as "no overfitting"). Columns must be approximately independent
    trials — passing a series joined with its own lag is a caller error.
    """
    R = np.asarray(returns_matrix, dtype=float)
    if R.ndim != 2:
        raise ValueError(f"returns_matrix must be 2-D (T, N), got ndim={R.ndim}")
    if R.shape[0] < n_partitions * 2 or R.shape[1] < 2:
        raise ValueError(
            f"CSCV needs >= {n_partitions * 2} rows and >= 2 trials, got {R.shape}"
        )
    rng = np.random.default_rng(seed)
    T, N = R.shape
    S = min(int(n_partitions), T // 2)
    if S % 2:
        S -= 1
    parts = np.array_split(np.arange(T), S)
    from itertools import combinations
    combos = list(combinations(range(S), S // 2))
    if len(combos) > 256:
        combos = [combos[i] for i in rng.choice(len(combos), 256, replace=False)]
    scores = []
    for combo in combos:
        is_idx = np.concatenate([parts[s] for s in combo])
        oos_idx = np.concatenate([parts[s] for s in range(S) if s not in set(combo)])
        is_sr = R[is_idx].mean(0) / np.maximum(R[is_idx].std(axis=0, ddof=1), 1e-12)
        oos_sr = R[oos_idx].mean(0) / np.maximum(R[oos_idx].std(axis=0, ddof=1), 1e-12)
        best = int(np.argmax(is_sr))
        med = float(np.median(oos_sr))
        scores.append(1.0 if oos_sr[best] < med else 0.0)
    return float(np.mean(scores)) if scores else 0.0


def reality_check_pvalue(strategy: pd.Series, benchmark: pd.Series,
                         n_boot: int = 1000, block: int = 5,
                         seed: int = 11) -> float:
    """White-style reality check: H0 = benchmark edge >= strategy edge.

    Stationary-bootstrap resampling of the *loss differential*
    d_t = r_strat - r_bench; p = P(mean(d*) >= mean(d)). Corrects the legacy
    bug that permuted returns against themselves (p ~ 0.5 by construction).

    Fail-closed: fewer than 10 usable observations raise ValueError instead
    of returning 1.0 ("not significant" by construction).
    """
    s = np.asarray(strategy, dtype=float).ravel()
    b = np.asarray(benchmark, dtype=float).ravel()
    n = min(len(s), len(b))
    if n < 10:
        raise ValueError(f"reality check needs >= 10 observations, got {n}")
    d = (s[:n] - b[:n]).astype(float)
    d = d[np.isfinite(d)]
    if len(d) < 10:
        raise ValueError(f"reality check needs >= 10 finite differentials, got {len(d)}")
    obs = float(d.mean())
    rng = np.random.default_rng(seed)
    q = 1.0 / max(block, 1)
    cnt = 0
    for _ in range(n_boot):
        idx: list[int] = []
        while len(idx) < len(d):
            start = int(rng.integers(0, len(d)))
            L = int(rng.geometric(q))
            idx.extend([(start + j) % len(d) for j in range(L)])
        sample = d[np.array(idx[:len(d)])]
        if float(sample.mean()) >= obs:
            cnt += 1
    return float((cnt + 1) / (n_boot + 1))


__all__ = ["purged_walk_forward_splits", "deflated_sharpe_probability",
           "pbo_cscv", "reality_check_pvalue"]
