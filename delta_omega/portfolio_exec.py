"""L5: mean-variance/HRP/Black-Litterman + sqrt impact. L6: OFI/microprice/VPIN/AC/SOR. FI+options."""
from __future__ import annotations
import math
import numpy as np

# ---------- costs ----------
def sqrt_impact_cost(dw: float, price: float, sigma: float, volume: float, spread: float, gamma: float = 0.5) -> float:
    if volume <= 0 or price <= 0 or sigma < 0 or spread < 0:
        raise ValueError("invalid market inputs for impact")
    notional = abs(dw) * price
    return spread*abs(dw) + gamma*sigma*math.sqrt(notional/max(volume,1e-18))*abs(dw)

def _proj_simplex_box(v: np.ndarray, lmax: float) -> np.ndarray:
    w = np.asarray(v, float)
    if lmax <= 0:
        raise ValueError("Lmax>0")
    Cairo = np.clip(w, -1, 1)
    g = float(np.sum(np.abs(Cairo)))
    return Cairo * min(1.0, lmax/max(g, 1e-18))

def mean_variance(alpha: np.ndarray, Sigma: np.ndarray, lam: float, lmax: float = 1.0,
                  adv_cap: np.ndarray | None = None, iters: int = 2000, lr: float = 1e-2) -> np.ndarray:
    """Projected gradient ascent on w'a - lam/2 w'Sw. Deterministic, fail-closed."""
    a = np.asarray(alpha, float); S = np.asarray(Sigma, float)
    n = a.size
    if S.shape != (n, n) or lam <= 0:
        raise ValueError("bad MVO inputs")
    w = np.zeros(n)
    for _ in range(iters):
        g = a - lam*(S @ w)
        w = _proj_simplex_box(w + lr*g, lmax)
        if adv_cap is not None:
            w = np.clip(w, -np.asarray(adv_cap, float), np.asarray(adv_cap, float))
    return w

def hrp_weights(cov: np.ndarray) -> np.ndarray:
    """Hierarchical Risk Parity (single-linkage proxy via sorted variance + recursive bisection)."""
    C = np.asarray(cov, float); n = C.shape[0]
    if C.shape != (n, n) or n == 0:
        raise ValueError("bad cov")
    order = np.argsort(np.diag(C))
    w = np.ones(n)
    def cluster_var(idx: list[int]) -> float:
        sub = C[np.ix_(idx, idx)]
        iv = 1.0/np.maximum(np.diag(sub), 1e-18)
        pv = iv/iv.sum()
        return float(pv @ sub @ pv)
    def bisect(idx: list[int]) -> None:
        if len(idx) <= 1:
            return
        h = len(idx)//2
        L, R = idx[:h], idx[h:]
        vL, vR = cluster_var(L), cluster_var(R)
        a = 1 - vL/max(vL+vR, 1e-18)
        w[L] *= a; w[R] *= (1-a)
        bisect(L); bisect(R)
    bisect(order.tolist())
    return w/w.sum()

def black_litterman(mu_prior: np.ndarray, Sigma: np.ndarray, P: np.ndarray, q: np.ndarray,
                    Omega: np.ndarray, tau: float = 0.05) -> np.ndarray:
    m = np.asarray(mu_prior, float); S = np.asarray(Sigma, float)
    P = np.asarray(P, float); q = np.asarray(q, float); Om = np.asarray(Omega, float)
    tS = tau*S
    M = np.linalg.inv(np.linalg.inv(tS) + P.T @ np.linalg.inv(Om) @ P)
    return M @ (np.linalg.inv(tS) @ m + P.T @ np.linalg.inv(Om) @ q)

# ---------- L6 microstructure ----------
def ofi_tick(pb: float, qb: float, pb_prev: float, qb_prev: float,
             pa: float, qa: float, pa_prev: float, qa_prev: float) -> float:
    dW = (qb if pb >= pb_prev else 0) - (qb_prev if pb <= pb_prev else 0) \
       - ((qa if pa <= pa_prev else 0) - (qa_prev if pa >= pa_prev else 0))
    return float(dW)

def microprice(pb: float, qb: float, pa: float, qa: float, ofi: float = 0.0, theta: float = 0.0) -> float:
    if qb + qa <= 0 or pa <= pb:
        raise ValueError("crossed/empty book (fail-closed)")
    return (qb*pa + qa*pb)/(qb+qa) + theta*ofi

def vpin(buys: np.ndarray, sells: np.ndarray, n_buckets: int = 50) -> float:
    b = np.asarray(buys, float); s = np.asarray(sells, float)
    if b.size != s.size or b.size < n_buckets:
        raise ValueError("VPIN needs aligned bucket series")
    imbal = np.abs(b[-n_buckets:] - s[-n_buckets:])
    tot = b[-n_buckets:] + s[-n_buckets:]
    return float(imbal.sum()/max(tot.sum(), 1e-18))

def almgren_chriss(n_shares: float, T: float, n_steps: int, sigma: float,
                   eta: float, gamma_: float, lam_risk: float) -> np.ndarray:
    """Optimal inventory trajectory x(t); closed-form kappa solution."""
    if n_steps < 2 or T <= 0 or sigma < 0 or eta <= 0:
        raise ValueError("bad AC inputs")
    kappa = math.sqrt(max(lam_risk*sigma*sigma/max(eta, 1e-18), 1e-18))
    t = np.linspace(0, T, n_steps)
    traj = n_shares * np.sinh(kappa*(T-t))/math.sinh(kappa*T)
    return traj

def sor_split(sizes: dict[str, float], total: float) -> dict[str, float]:
    """Pro-rata SOR across venues by displayed size. Fail-closed on empty book."""
    tot = sum(sizes.values())
    if tot <= 0 or total <= 0:
        raise ValueError("no venue liquidity")
    return {v: total*s/max(tot, 1e-18) for v, s in sizes.items()}

# ---------- W107/W108 FI + options ----------
def nss_rate(t: float, b0: float, b1: float, b2: float, b3: float, l1: float, l2: float) -> float:
    t = max(t, 1e-9)
    e1, e2 = math.exp(-t/l1), math.exp(-t/l2)
    return b0 + b1*(1-e1)/(t/l1) + b2*((1-e1)/(t/l1)-e1) + b3*((1-e2)/(t/l2)-e2)

def _phi(x: float) -> float:
    return 0.5*(1+math.erf(x/math.sqrt(2)))

def bs_price(S: float, K: float, T: float, r: float, vol: float, kind: str = "call") -> float:
    if S <= 0 or K <= 0 or T <= 0 or vol <= 0:
        raise ValueError("bad BS inputs")
    d1 = (math.log(S/K)+(r+0.5*vol*vol)*T)/(vol*math.sqrt(T))
    d2 = d1 - vol*math.sqrt(T)
    df = math.exp(-r*T)
    if kind == "call":
        return _phi(d1)*S - _phi(d2)*K*df
    if kind == "put":
        return _phi(-d2)*K*df - _phi(-d1)*S
    raise ValueError("kind call|put")

def bs_delta(S: float, K: float, T: float, r: float, vol: float, kind: str = "call") -> float:
    if S <= 0 or K <= 0 or T <= 0 or vol <= 0:
        raise ValueError("bad BS inputs")
    d1 = (math.log(S/K)+(r+0.5*vol*vol)*T)/(vol*math.sqrt(T))
    return _phi(d1) if kind == "call" else _phi(d1)-1.0

# ---------- Bridge aliases (Step 1.1): canonical names used by the live engine ----------
# The math above is the single source of truth; the names below are thin aliases
# so legacy call-sites and new docs agree on one price source per scan.

def sqrt_transient_impact(dw: float, price: float, sigma: float, volume: float, spread: float, gamma: float = 0.5) -> float:
    """Canonical alias of sqrt_impact_cost (bridge name used by backtest engine)."""
    return sqrt_impact_cost(dw, price, sigma, volume, spread, gamma)


def execution_price(mid: float, side: str, qty_shares: float, sigma: float,
                    market_volume_shares: float, spread: float, gamma: float = 0.5) -> float:
    """Execution price per the wired fill model (Step 1.1)::

        P_fill = P_mid +/- (spread/2 + gamma * sigma * sqrt(V_order / V_market))

    ``side`` is ``"buy"`` (pay the ask side) or ``"sell"`` (hit the bid side).
    Fail-closed on non-positive price/volume inputs.
    """
    if mid <= 0 or market_volume_shares <= 0 or sigma < 0 or spread < 0 or qty_shares < 0:
        raise ValueError("invalid execution inputs (fail-closed)")
    import math as _math
    half_spread = spread / 2.0
    impact = gamma * sigma * _math.sqrt(qty_shares / market_volume_shares) * mid
    if side == "buy":
        return mid + half_spread + impact
    if side == "sell":
        return mid - half_spread - impact
    raise ValueError("side must be 'buy'|'sell'")


class AlmgrenChrissTrajectory:
    """Bridge wrapper around almgren_chriss (Step 1.1).

    Splits orders with V_order > 10% of market volume into AC-optimal slices.
    """

    ADV_SPLIT_THRESHOLD = 0.10

    def __init__(self, n_shares: float, T: float, n_steps: int, sigma: float,
                 eta: float, gamma_: float, lam_risk: float) -> None:
        self.trajectory = almgren_chriss(n_shares, T, n_steps, sigma, eta, gamma_, lam_risk)

    @staticmethod
    def needs_slicing(order_qty: float, market_volume: float, threshold: float = 0.10) -> bool:
        if market_volume <= 0:
            raise ValueError("market volume must be positive (fail-closed)")
        return abs(order_qty) > threshold * market_volume

    @staticmethod
    def slice_order(order_qty: float, market_volume: float, n_slices: int) -> list[float]:
        if n_slices < 1:
            raise ValueError("n_slices >= 1")
        base = order_qty / n_slices
        return [base] * n_slices


def sabr_iv(F: float, K: float, T: float, alpha: float, beta: float, rho: float, nu: float) -> float:
    """Hagan SABR lognormal implied vol."""
    if F <= 0 or K <= 0 or T <= 0 or alpha <= 0 or nu < 0 or not -1 < rho < 1:
        raise ValueError("bad SABR inputs")
    if abs(F-K) < 1e-12:
        f = F**(1-beta)
        t1 = alpha/f
        t2 = (1-beta)**2/24*alpha*alpha/(F**(2-2*beta)) + rho*beta*nu*alpha/(4*F**(1-beta)) + (2-3*rho*rho)/24*nu*nu
        return t1*(1+T*t2)
    z = nu/alpha*(F*K)**((1-beta)/2)*math.log(F/K)
    xz = math.log((math.sqrt(1-2*rho*z+z*z)+z-rho)/(1-rho))
    fk = (F*K)**((1-beta)/2)*(1+(1-beta)**2/24*math.log(F/K)**2+(1-beta)**4/1920*math.log(F/K)**4)
    t2 = (1-beta)**2/24*alpha*alpha/(F*K)**(1-beta) + rho*beta*nu*alpha/(4*(F*K)**((1-beta)/2)) + (2-3*rho*rho)/24*nu*nu
    return alpha/fk*z/xz*(1+T*t2)
