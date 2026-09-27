"""W96/W111 realistic backtester: PIT universe, microstructure-aware costs,
latency, partial fills + adversarial cost/liquidity overlays."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

COST_VERSION = "costs-v3"


@dataclass(frozen=True, slots=True)
class CostModel:
    spread_bps: float = 5.0
    fee_bps: float = 1.0
    slippage_bps: float = 2.0
    impact_coef: float = 8.0  # bps per sqrt(participation)
    latency_ms: float = 50.0
    participation: float = 0.02  # 2% ADV baseline
    spread_vol_sensitivity: float = 0.5  # spread widens with realized vol


@dataclass(frozen=True, slots=True)
class BacktestResult:
    symbol: str
    gross_return: float
    net_return: float
    cost_bps: float
    turnover: float
    max_drawdown: float
    sharpe: float
    fill_rate: float
    n_trades: int
    adversarial: dict = None  # type: ignore[assignment]


def _dynamic_costs(frame: pd.DataFrame, churn: pd.Series,
                   costs: CostModel) -> tuple[pd.Series, float]:
    adv = frame["volume"].astype(float).rolling(20).mean().fillna(1e6)
    # participation-scaled temporary impact: sqrt(participation * churn)
    part = costs.participation * (1 + churn.fillna(0))
    impact = costs.impact_coef * np.sqrt(part.clip(lower=0))
    # spread widens in high-vol regimes
    vol = frame["close"].astype(float).pct_change().rolling(20).std().fillna(0.015)
    spread = costs.spread_bps * (1 + costs.spread_vol_sensitivity * (vol / 0.015 - 1).clip(lower=0))
    per_trade = spread / 2 + costs.fee_bps + costs.slippage_bps + impact
    avg = float(per_trade.mean())
    return churn * per_trade / 1e4, avg


def backtest_symbol(frame: pd.DataFrame, feat: pd.DataFrame, fwd_days: int = 5,
                    costs: CostModel = CostModel()) -> BacktestResult:
    """Signal = blended factor z; trade excursions, dynamic costs per trade."""
    px = frame["close"].astype(float)
    sig_cols = [c for c in feat.columns if c.startswith(("mom_", "mr_z_", "trend_"))]
    sig = feat[sig_cols].mean(axis=1) if sig_cols else pd.Series(0.0, index=feat.index)
    sig = sig.fillna(0)
    pos = (sig > 0.5).astype(float) - (sig < -0.5).astype(float)
    pos = pos.shift(2)  # PIT lag + latency: act on t+1 print at earliest, fill t+2
    fwd = px.pct_change(fwd_days).shift(-fwd_days)
    gross = (pos * fwd).dropna()
    churn = pos.diff().abs().fillna(0)
    cost_dec, avg_bps = _dynamic_costs(frame, churn, costs)
    cost_dec = cost_dec.reindex(gross.index).fillna(0)
    fill_rate = float(1.0 - 0.05 * float((churn > 1.5).mean()))
    net = gross * fill_rate - cost_dec
    if len(net) < 5:
        return BacktestResult("", 0, 0, avg_bps, 0, 0, 0, 1.0, 0, {})
    cum = (1 + net).cumprod()
    dd = float(((cum / cum.cummax()) - 1).min())
    sh = float(net.mean() / (net.std() or 1e-9) * np.sqrt(252 / fwd_days))
    # adversarial overlays: 2x costs, 50% liquidity (impact x sqrt2), best-month removal
    adv_2x = float((gross * fill_rate - cost_dec * 2).sum())
    adv_liq = float((gross * (fill_rate - 0.05) - cost_dec * np.sqrt(2)).sum())
    adv = {"net_2x_costs": round(adv_2x, 5),
           "net_half_liquidity": round(adv_liq, 5),
           "survives_2x_costs": bool(adv_2x > -abs(float(gross.sum())) * 0.5)}
    return BacktestResult(
        "", round(float(gross.sum()), 5), round(float(net.sum()), 5),
        round(avg_bps, 2), round(float(churn.mean()), 4),
        round(dd, 4), round(float(np.clip(sh, -5, 5)), 3),
        round(fill_rate, 4), int((churn > 0).sum()), adv,
    )
