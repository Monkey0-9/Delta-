"""DELTA OS quant kit: VWAP bands, fractional Kelly, VaR/CVaR, ATR, beta.

Pure functions over pandas/numpy; no network, no state. Conventions match the
research path (historical simulation, 252-day annualization) so terminal
numbers agree with the lab.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

QUANTKIT_VERSION = "quantkit-v1"


def vwap_bands(frame: pd.DataFrame, window: int = 20) -> pd.DataFrame:
    """Rolling VWAP with VOLUME-WEIGHTED sigma (blueprint formula):

        VWAP_t = sum(P*V)/sum(V);  sigma_t = sqrt(sum(V*(P-VWAP)^2)/sum(V))

    Bands at +-1/2/3 sigma: fair value / exhaustion / extreme deviation."""
    tp = ((frame["high"].astype(float) + frame["low"].astype(float)
           + frame["close"].astype(float)) / 3)
    vol = frame["volume"].astype(float).clip(lower=1)
    vwap = (tp * vol).rolling(window).sum() / vol.rolling(window).sum()
    dev2 = (vol * (tp - vwap) ** 2).rolling(window).sum() / vol.rolling(window).sum()
    sd = np.sqrt(dev2.clip(lower=0))
    return pd.DataFrame({"vwap": vwap, "upper1": vwap + sd, "lower1": vwap - sd,
                         "upper2": vwap + 2 * sd, "lower2": vwap - 2 * sd,
                         "upper3": vwap + 3 * sd, "lower3": vwap - 3 * sd},
                        index=frame.index)


def vwap_location(price: float, bands_row: pd.Series) -> float:
    """Position of price in VWAP sigma units (for execution cards)."""
    sd = (bands_row["upper1"] - bands_row["vwap"]) or 1e-9
    return round(float((price - bands_row["vwap"]) / sd), 2)


def volume_profile(frame: pd.DataFrame, bins: int = 24) -> dict:
    """Point of Control + 70% value area (VAH/VAL) over the frame window."""
    h, l, c = (frame["high"].astype(float), frame["low"].astype(float),
               frame["close"].astype(float))
    tp = (h + l + c) / 3
    vol = frame["volume"].astype(float).clip(lower=0)
    lo, hi = float(l.min()), float(h.max())
    if hi <= lo or float(vol.sum()) <= 0:
        raise ValueError("degenerate frame for volume profile.")
    edges = np.linspace(lo, hi, bins + 1)
    idx = np.clip(np.digitize(tp.to_numpy(), edges) - 1, 0, bins - 1)
    prof = np.bincount(idx, weights=vol.to_numpy(), minlength=bins)
    poc = int(np.argmax(prof))
    total = prof.sum()
    lo_i = hi_i = poc
    acc = prof[poc]
    while acc < 0.70 * total and (lo_i > 0 or hi_i < bins - 1):
        down = prof[lo_i - 1] if lo_i > 0 else -1
        up = prof[hi_i + 1] if hi_i < bins - 1 else -1
        if up >= down and hi_i < bins - 1:
            hi_i += 1
            acc += prof[hi_i]
        elif lo_i > 0:
            lo_i -= 1
            acc += prof[lo_i]
        else:
            break
    mid = lambda i: round(float((edges[i] + edges[i + 1]) / 2), 4)
    return {"poc": mid(poc), "vah": mid(hi_i), "val": mid(lo_i),
            "coverage": round(float(acc / total), 3), "bins": bins}


def atr(frame: pd.DataFrame, window: int = 14) -> pd.Series:
    h, l, c = (frame["high"].astype(float), frame["low"].astype(float),
               frame["close"].astype(float))
    tr = pd.concat([(h - l), (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    return tr.rolling(window).mean()


def fractional_kelly(p: float, b: float, c: float = 0.5) -> float:
    """f = c*(p*b - q)/b, c in [0.25, 0.5]. p=win prob, b=win/loss ratio."""
    if not 0 < p < 1 or b <= 0:
        raise ValueError("need 0<p<1 and b>0.")
    c = min(0.5, max(0.25, c))
    return round(max(0.0, c * (p * b - (1 - p)) / b), 4)


def var_cvar(rets: pd.Series, level: float = 0.95, capital: float = 1.0) -> dict:
    """Historical + parametric (normal) VaR/CVaR as fraction-of-capital losses."""
    x = rets.dropna().astype(float)
    if len(x) < 10:
        raise ValueError("need >= 10 returns.")
    import math

    q = 1 - level
    hvar = float(-x.quantile(q) * capital)
    hcvar = float(-x[x <= x.quantile(q)].mean() * capital)
    mu, sd = float(x.mean()), float(x.std())
    z = {0.95: 1.645, 0.99: 2.326}.get(level, 1.645)
    pvar = max(-(mu - z * sd), 0.0) * capital
    phi = math.exp(-z * z / 2) / math.sqrt(2 * math.pi)
    pcvar = (-mu + sd * phi / (1 - level)) * capital
    return {"level": level, "hist_var": round(hvar, 4), "hist_cvar": round(hcvar, 4),
            "param_var": round(float(pvar), 4), "param_cvar": round(float(pcvar), 4)}


def beta_to_market(asset: pd.Series, market: pd.Series) -> float:
    a, m = asset.dropna().astype(float), market.dropna().astype(float)
    idx = a.index.intersection(m.index)
    if len(idx) < 10:
        raise ValueError("need >= 10 overlapping returns.")
    a, m = a.reindex(idx), m.reindex(idx)
    return round(float(np.cov(a, m)[0, 1] / (np.var(m) or 1e-12)), 3)


def sharpe_maxdd(equity: pd.Series) -> dict:
    r = equity.astype(float).pct_change().dropna()
    sh = float(r.mean() / (r.std() or 1e-9) * np.sqrt(252)) if len(r) > 3 else 0.0
    dd = float(((equity / equity.cummax()) - 1).min()) if len(equity) else 0.0
    return {"sharpe": round(sh, 3), "max_drawdown": round(dd, 4)}


# ---------------- fundamentals (pure: dict in, scores out) ----------------

def piotroski_f(fin: dict) -> dict:
    """Nine-point F-Score from profitability/leverage/liquidity/efficiency.

    Expects keys: roa, cfo, delta_roa, accrual (cfo-roa), delta_lever,
    delta_liquid, shares_issued (bool), delta_gm, delta_turn. Each worth 1pt.
    """
    try:
        pts = {
            "roa>0": fin["roa"] > 0,
            "cfo>0": fin["cfo"] > 0,
            "roa_up": fin["delta_roa"] > 0,
            "accrual_ok": fin["cfo"] > fin["roa"],
            "lever_down": fin["delta_lever"] <= 0,
            "liquid_up": fin["delta_liquid"] > 0,
            "no_dilution": not fin["shares_issued"],
            "gm_up": fin["delta_gm"] > 0,
            "turn_up": fin["delta_turn"] > 0,
        }
    except KeyError as exc:
        raise ValueError(f"missing fundamental field: {exc}") from exc
    score = sum(pts.values())
    return {"score": score, "max": 9, "detail": pts,
            "grade": "STRONG" if score >= 7 else ("WEAK" if score <= 2 else "AVERAGE")}


def altman_z(fin: dict) -> dict:
    """Altman Z (manufacturing): 1.2A+1.4B+3.3C+0.6D+1.0E.

    Keys: wc_ta, re_ta, ebit_ta, mve_tl, sales_ta. Zones: >2.99 safe,
    1.81-2.99 grey, <1.81 distress.
    """
    try:
        z = (1.2 * fin["wc_ta"] + 1.4 * fin["re_ta"] + 3.3 * fin["ebit_ta"]
             + 0.6 * fin["mve_tl"] + 1.0 * fin["sales_ta"])
    except KeyError as exc:
        raise ValueError(f"missing fundamental field: {exc}") from exc
    z = round(float(z), 2)
    return {"z": z, "zone": "SAFE" if z > 2.99 else ("DISTRESS" if z < 1.81 else "GREY")}


def dcf_value(fcf: float, growth_5y: float, wacc: float, terminal_g: float,
              years: int = 5, shares: float = 1.0, net_debt: float = 0.0) -> dict:
    """Multi-stage DCF: explicit FCF growth, Gordon terminal. All rates decimal."""
    if not 0 < wacc < 1 or shares <= 0 or fcf <= 0:
        raise ValueError("need 0<wacc<1, shares>0, fcf>0.")
    if terminal_g >= wacc:
        raise ValueError("terminal growth must be < WACC.")
    pv = sum(fcf * (1 + growth_5y) ** t / (1 + wacc) ** t for t in range(1, years + 1))
    term = (fcf * (1 + growth_5y) ** years * (1 + terminal_g) / (wacc - terminal_g)
            / (1 + wacc) ** years)
    equity = pv + term - net_debt
    return {"enterprise_value": round(pv + term, 2),
            "equity_value": round(equity, 2),
            "per_share": round(equity / shares, 2)}

# ---------------- microstructure (OBI, Greeks, sizing, impact) ----------------

def obi(bid_vol: float, ask_vol: float) -> float:
    """Order-book imbalance in [-1, +1]: (Vbid-Vask)/(Vbid+Vask)."""
    denom = float(bid_vol) + float(ask_vol)
    if denom <= 0:
        return 0.0
    return round((float(bid_vol) - float(ask_vol)) / denom, 4)


def bs_price_greeks(s: float, k: float, t: float, r: float, sigma: float,
                    kind: str = "call") -> dict:
    """Black-Scholes price + delta/gamma/theta/vega (t in years). Pure numpy."""
    import math as _m
    if s <= 0 or k <= 0 or t <= 0 or sigma <= 0:
        raise ValueError("need s,k,t,sigma > 0.")
    d1 = (_m.log(s / k) + (r + 0.5 * sigma ** 2) * t) / (sigma * _m.sqrt(t))
    d2 = d1 - sigma * _m.sqrt(t)
    nd = lambda x: 0.5 * (1 + _m.erf(x / _m.sqrt(2)))
    pdf = _m.exp(-0.5 * d1 * d1) / _m.sqrt(2 * _m.pi)
    disc = _m.exp(-r * t)
    if kind == "call":
        price = s * nd(d1) - k * disc * nd(d2)
        delta = nd(d1)
    elif kind == "put":
        price = k * disc * nd(-d2) - s * nd(-d1)
        delta = nd(d1) - 1.0
    else:
        raise ValueError("kind must be call|put.")
    return {"price": round(price, 4), "delta": round(delta, 4),
            "gamma": round(pdf / (s * sigma * _m.sqrt(t)), 6),
            "theta": round(-(s * pdf * sigma) / (2 * _m.sqrt(t)) / 365.0, 4),
            "vega": round(s * pdf * _m.sqrt(t) / 100.0, 4)}


def fractional_shares(notional: float, price: float, min_notional: float = 1.0) -> float:
    """Fractional share qty down to $1 notional (Alpaca-style)."""
    if price <= 0 or notional < min_notional:
        raise ValueError("need price>0 and notional>=min_notional ($1).")
    return round(float(notional) / float(price), 6)


def kelly_position_size(equity: float, price: float, p: float, b: float,
                        frac: float = 0.25) -> dict:
    """Conservative 0.25-Kelly share sizing: 5 drawdowns cost <4% capital."""
    f = fractional_kelly(p, b, c=frac)
    notional = equity * f
    qty = fractional_shares(notional, price) if notional >= 1.0 else 0.0
    return {"kelly_f": f, "notional": round(notional, 2), "qty": qty,
            "equity_pct": round(f, 4)}


def spread_drag_bps(spread: float, price: float) -> float:
    """Spread cost in bps (half-spread cross)."""
    if price <= 0:
        return 0.0
    return round(float(spread) / float(price) * 10_000 / 2.0, 2)


def market_impact_bps(qty: float, price: float, adv_shares: float,
                      atr_val: float = 0.0) -> dict:
    """Square-root impact: 8*sqrt(participation)*100 bps + ATR kicker."""
    part = (qty * price) / max(adv_shares * price, 1e-9)
    bps = 8.0 * (max(part, 0.0) ** 0.5) * 100
    if atr_val and price:
        bps += (atr_val / price) * 10_000 * 0.05 * part
    return {"participation": round(part, 6), "impact_bps": round(bps, 2)}


def sortino_maxdd(equity) -> dict:
    """Sortino (downside-dev, 252d) + MaxDD. Complements sharpe_maxdd."""
    r = equity.astype(float).pct_change().dropna()
    down = r[r < 0]
    dd_vol = float(down.std()) if len(down) > 2 else 0.0
    sortino = float(r.mean() / (dd_vol or 1e-9) * np.sqrt(252)) if len(r) > 3 else 0.0
    dd = float(((equity / equity.cummax()) - 1).min()) if len(equity) else 0.0
    return {"sortino": round(sortino, 3), "max_drawdown": round(dd, 4)}


def risk_reward(price: float, stop: float | None, target: float | None) -> float | None:
    """Reward/risk ratio. None when stop/target missing."""
    if stop is None or target is None or price is None:
        return None
    risk = abs(price - stop) or 1e-9
    return round(abs(target - price) / risk, 2)


# ---------------- execution algos ----------------

def twap_schedule(quantity: float, slices: int, interval_s: float = 60.0) -> list[dict]:
    """Time-weighted slices: equal qty per slice, deterministic timestamps offsets."""
    if quantity <= 0 or slices < 1 or int(slices) != slices:
        raise ValueError("need quantity>0 and integer slices>=1.")
    slices = int(slices)
    base, rem = divmod(round(quantity, 8), slices)
    out = []
    for i in range(slices):
        q = base + (round(rem, 8) if i == slices - 1 else 0.0)
        out.append({"slice": i + 1, "of": slices, "qty": round(q, 8),
                    "at_offset_s": round(i * interval_s, 1)})
    return out


def post_only_allowed(side: str, limit: float, ref_bid: float, ref_ask: float) -> tuple[bool, str]:
    """Post-only: buy must rest BELOW best ask, sell ABOVE best bid."""
    side = side.lower()
    if side == "buy":
        return (limit < ref_ask, "resting" if limit < ref_ask else "would take -> refused")
    if side == "sell":
        return (limit > ref_bid, "resting" if limit > ref_bid else "would take -> refused")
    raise ValueError("side must be buy|sell.")


__all__ = ["QUANTKIT_VERSION", "vwap_bands", "vwap_location", "volume_profile",
           "atr", "fractional_kelly", "var_cvar",
           "beta_to_market", "sharpe_maxdd", "piotroski_f", "altman_z",
           "dcf_value", "twap_schedule", "post_only_allowed",
           "obi", "bs_price_greeks", "fractional_shares",
           "kelly_position_size", "spread_drag_bps", "market_impact_bps",
           "sortino_maxdd", "risk_reward"]
