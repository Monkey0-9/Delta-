"""L3: orthogonalization + DSR + CPCV/PBO. L4: Ledoit-Wolf, factor risk, EVT VaR/ES, stress."""
from __future__ import annotations
import math
import numpy as np

# ---------- L3 ----------
def orthogonalize(alpha_new: np.ndarray, Q: np.ndarray, min_ratio: float = 0.25) -> np.ndarray:
    """SVD projection onto complement of span(Q). Rejects when residual-ratio
    ||P_perp a||/||a|| < min_ratio. SVD (not QR) so rank-deficient / collinear /
    NaN-padded factor blocks cannot silently collapse the projection."""
    a = np.asarray(alpha_new, float).reshape(-1)
    nrm_a = float(np.linalg.norm(a))
    if not math.isfinite(nrm_a) or nrm_a < 1e-12:
        raise ValueError("zero/non-finite alpha vector")
    if Q.size == 0:
        return a / nrm_a
    Qm = np.asarray(Q, float)
    if Qm.ndim == 1:
        Qm = Qm.reshape(-1, 1)
    if not np.all(np.isfinite(Qm)):
        raise ValueError("non-finite factor block (fail-closed)")
    u, s, _ = np.linalg.svd(Qm, full_matrices=False)
    rank = int((s > max(Qm.shape) * np.finfo(float).eps * (s[0] if s.size else 1.0)).sum())
    q = u[:, :rank]
    p = a - q @ (q.T @ a)
    ratio = float(np.linalg.norm(p)) / nrm_a
    if ratio < min_ratio:
        raise ValueError(f"redundant alpha: residual-ratio {ratio:.4f} < {min_ratio}")
    return p / float(np.linalg.norm(p))

def expected_max_sharpe(n_trials: int) -> float:
    g = 0.5772156649
    if n_trials < 2:
        return 0.0
    return float(math.sqrt(2*math.log(n_trials))*(1-g/math.sqrt(2*math.log(n_trials)))
                 + math.log(4*math.pi*math.log(n_trials))/(2*math.sqrt(2*math.log(n_trials))))

def deflated_sharpe(sr: float, n_trials: int, T: int, skew: float, kurt: float) -> float:
    """DSR = Phi((sr - sr0)*sqrt(T-1) / sqrt(1 - skew*sr + (kurt-1)/4*sr^2))."""
    from math import erf
    sr0 = expected_max_sharpe(n_trials)
    denom = math.sqrt(max(1e-12, 1 - skew*sr + (kurt-1)/4*sr*sr))
    z = (sr - sr0)*math.sqrt(max(T-1, 1)) / denom
    return 0.5*(1+erf(z/math.sqrt(2)))

def require_dsr(sr: float, n_trials: int, T: int, skew: float, kurt: float, bar: float = 0.99) -> float:
    d = deflated_sharpe(sr, n_trials, T, skew, kurt)
    if d < bar:
        raise ValueError(f"DSR rejection: {d:.4f} < {bar}")
    return d

def cpcv_splits(n_obs: int, n_partitions: int = 6, n_test: int = 2, embargo_pct: float = 0.01):
    """Combinatorial purged CV split generator: yield (train_idx, test_idx) over all
    C(n_partitions, n_test) combos, purging train obs within embargo of any test obs."""
    from itertools import combinations
    if n_obs < n_partitions or n_test >= n_partitions or n_partitions < 2:
        raise ValueError("bad CPCV geometry")
    bounds = np.array_split(np.arange(n_obs), n_partitions)
    embargo = max(1, int(n_obs * embargo_pct))
    for test_parts in combinations(range(n_partitions), n_test):
        test_idx = np.concatenate([bounds[i] for i in test_parts])
        lo, hi = int(test_idx.min()), int(test_idx.max())
        train_idx = np.concatenate([bounds[i] for i in range(n_partitions) if i not in test_parts])
        train_idx = train_idx[(train_idx < lo - embargo) | (train_idx > hi + embargo)]
        if train_idx.size == 0:
            raise ValueError("embargo purged entire train set: widen data or shrink embargo")
        yield train_idx, test_idx

def pbo(is_sharpes: np.ndarray, oos_sharpes: np.ndarray) -> float:
    """Lopez de Prado PBO: S splits x N trials. For each split, rank trials by IS
    Sharpe; PBO = fraction of splits where the best-IS trial's OOS rank is below median."""
    IS = np.asarray(is_sharpes, float); OOS = np.asarray(oos_sharpes, float)
    if IS.shape != OOS.shape or IS.ndim != 2 or IS.shape[0] < 2:
        raise ValueError("PBO needs S>=2 x N Sharpe matrices (splits x trials)")
    S, N = IS.shape
    below = 0
    for s in range(S):
        best = int(np.argmax(IS[s]))
        rank = int((OOS[s] > OOS[s, best]).sum()) + 1  # 1 = best
        if rank > (N + 1) / 2:
            below += 1
    return below / S

def pbo_from_cscv(is_sharpes: np.ndarray, oos_sharpes: np.ndarray) -> float:
    """Single-split PBO fallback. Prefer pbo() with a full split matrix."""
    is_s = np.asarray(is_sharpes, float); oos = np.asarray(oos_sharpes, float)
    if is_s.shape != oos.shape or is_s.size == 0:
        raise ValueError("IS/OOS sharpe arrays must be non-empty and aligned")
    return pbo(is_s.reshape(1, -1), oos.reshape(1, -1))

# ---------- L4 ----------
def ledoit_wolf_shrinkage(X: np.ndarray, target: str = "equicorr") -> tuple[np.ndarray, float]:
    """Linear Ledoit-Wolf shrinkage toward equi-correlation/single-factor target. X: (T,N)."""
    X = np.asarray(X, float)
    T, N = X.shape
    if T < 3 or N < 1:
        raise ValueError("insufficient observations for covariance")
    S = np.cov(X, rowvar=False)
    if N == 1:
        return S.reshape(1, 1), 0.0
    var = np.diag(S)
    mean_var = float(np.mean(var))
    corr = S / np.sqrt(np.outer(var, var) + 1e-18)
    rho = float((np.sum(corr) - N) / (N*(N-1)))
    F = np.sqrt(np.outer(var, var)) * rho + np.diag(var*(1-rho))
    # LW optimal delta via Frobenius-norm estimator (simplified analytic)
    Xc = X - X.mean(axis=0)
    pi = float(np.sum([np.sum((np.outer(x, x) - S)**2) for x in Xc]) / T)
    gamma = float(np.sum((S - F)**2))
    delta = float(min(1.0, max(0.0, pi / (T * max(gamma, 1e-18)))))
    return delta*F + (1-delta)*S, delta

def factor_portfolio_var(w: np.ndarray, B: np.ndarray, Omega: np.ndarray, D: np.ndarray) -> tuple[float, np.ndarray]:
    """V = w'(B Omega B' + diag(D))w; returns (total var, MCTR vector)."""
    w = np.asarray(w, float); B = np.asarray(B, float)
    Omega = np.asarray(Omega, float); D = np.asarray(D, float)
    Sigma = B @ Omega @ B.T + np.diag(D)
    v = float(w @ Sigma @ w)
    mctr = (w * (Sigma @ w)) / max(v, 1e-18)
    return v, mctr

def _gpd_mle(exc: np.ndarray) -> tuple[float, float, bool]:
    """MLE of GPD(xi, beta) on exceedances. Returns (xi, beta, converged). Falls back to MoM only if MLE fails."""
    from scipy.optimize import minimize
    m1 = float(exc.mean()); m2 = float((exc**2).mean())
    xi0 = float(min(0.4, max(-0.2, 0.5*(1 - m1*m1/max(m2 - m1*m1, 1e-18)))))
    b0 = max(m1*0.8, 1e-9)
    def nll(p: np.ndarray) -> float:
        xi, beta = float(p[0]), float(p[1])
        if beta <= 0 or xi <= -0.75 or xi >= 2.0:
            return 1e18
        if np.any(1 + xi*exc/beta <= 0):
            return 1e18
        k = exc.size
        return k*math.log(beta) + (1 + 1/xi)*np.log(1 + xi*exc/beta).sum() if abs(xi) > 1e-6 else k*math.log(beta) + exc.sum()/beta
    try:
        r = minimize(nll, np.array([xi0, b0]), method="Nelder-Mead",
                     options={"maxiter": 2000, "xatol": 1e-8, "fatol": 1e-8})
        if r.success and math.isfinite(float(r.fun)) and float(r.fun) < 1e17:
            return float(r.x[0]), max(float(r.x[1]), 1e-12), True
    except Exception:
        pass
    xi = float(min(0.9, max(-0.5, xi0)))
    beta = float(0.5*m1*(m2/max(m1*m1, 1e-18) + 1)) if abs(xi) > 1e-6 else m1
    return xi, max(beta, 1e-12), False

def evt_var_es(losses: np.ndarray, alpha: float = 0.99, u_quantile: float = 0.90) -> tuple[float, float]:
    """POT-GPD tail fit via MLE (MoM start, MoM fallback if optimizer fails) -> VaR_alpha, ES_alpha."""
    L = np.sort(np.asarray(losses, float))
    if L.size < 50:
        raise ValueError("EVT needs >=50 loss observations")
    if not 0 < alpha < 1:
        raise ValueError("alpha in (0,1)")
    u = float(np.quantile(L, u_quantile))
    exc = L[L > u] - u
    Nu = exc.size
    if Nu < 10:
        raise ValueError("too few tail exceedances")
    xi, beta, _ = _gpd_mle(exc)
    N = L.size
    var = u + beta/xi*(((N/Nu)*(1-alpha))**(-xi) - 1) if abs(xi) > 1e-6 else u - beta*math.log((N/Nu)*(1-alpha))
    es = var/(1-xi) + (beta - xi*u)/(1-xi)
    return float(var), float(es)

def stress_matrix(returns: np.ndarray, shocks: list[np.ndarray]) -> np.ndarray:
    """Apply historical/hypothetical shock vectors to return panel -> scenario P&L per unit weight."""
    R = np.asarray(returns, float)
    out = []
    for s in shocks:
        s = np.asarray(s, float)
        if s.shape != (R.shape[1],):
            raise ValueError("shock dim mismatch")
        out.append(R.mean(axis=0) + s)
    return np.array(out)

def reverse_stress(w: np.ndarray, Sigma: np.ndarray, loss_level: float) -> np.ndarray:
    """Worst direction r (unit Mahalanobis) s.t. w'r = -loss_level: r* = -loss*Sigma w / (w'Sigma w)."""
    w = np.asarray(w, float); Sigma = np.asarray(Sigma, float)
    denom = float(w @ Sigma @ w)
    if denom <= 0:
        raise ValueError("non-positive portfolio variance")
    return -loss_level * (Sigma @ w) / denom


# ---------- Bridge alias (Step 1.2): canonical SVD gate name used by signal layer ----------
def svd_orthogonalize(alpha_new: np.ndarray, Q: np.ndarray, min_ratio: float = 0.25) -> np.ndarray:
    """Canonical alias of orthogonalize (SVD projection, fail-closed).

    Thin alias so the live signal generator and docs share one name.
    Rejects (raises ValueError) when residual-variance ratio < min_ratio.
    """
    return orthogonalize(alpha_new, Q, min_ratio)
