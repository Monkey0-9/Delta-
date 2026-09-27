"""W96 realistic backtester: PIT universe, costs, impact, latency, partial fills."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

COST_VERSION = "costs-v2"


@dataclass(frozen=True, slots=True)
class CostModel:
    spread_bps: float = 5.0
    fee_bps: float = 1.0
    slippage_bps: float = 2.0
    impact_coef: float = 8.0  # bps per sqrt(participation)
    latency_ms: float = 50.0


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


def backtest_symbol(frame: pd.DataFrame, feat: pd.DataFrame, fwd_days: int = 5,
                    costs: CostModel = CostModel()) -> BacktestResult:
    """Signal = blended factor z; trade top/bottom excursions, costs per trade."""
    px = frame["close"].astype(float)
    sig_cols = [c for c in feat.columns if c.startswith(("mom_", "mr_z_", "trend_"))]
    sig = feat[sig_cols].mean(axis=1) if sig_cols else pd.Series(0.0, index=feat.index)
    sig = sig.fillna(0)
    pos = (sig > 0.5).astype(float) - (sig < -0.5).astype(float)
    pos = pos.shift(2)  # PIT lag + latency: act on t+1 print at earliest, fill t+2
    fwd = px.pct_change(fwd_days).shift(-fwd_days)
    gross = (pos * fwd).dropna()
    # costs: each position change pays spread+fee+slippage+impact
    churn = pos.diff().abs().fillna(0)
    adv = frame["volume"].astype(float).rolling(20).mean().fillna(1e6)
    notional_frac = 0.02  # 2% ADV participation assumption
    impact = costs.impact_coef * np.sqrt(notional_frac)
    per_trade_bps = costs.spread_bps / 2 + costs.fee_bps + costs.slippage_bps + impact
    cost_dec = churn * per_trade_bps / 1e4
    cost_dec = cost_dec.reindex(gross.index).fillna(0)
    # partial fills: 5% of large churn unfilled -> haircut gross
    fill_rate = float(1.0 - 0.05 * float((churn > 1.5).mean()))
    net = gross * fill_rate - cost_dec
    if len(net) < 5:
        return BacktestResult("", 0, 0, per_trade_bps, 0, 0, 0, 1.0, 0)
    cum = (1 + net).cumprod()
    dd = float(((cum / cum.cummax()) - 1).min())
    sh = float(net.mean() / (net.std() or 1e-9) * np.sqrt(252 / fwd_days))
    return BacktestResult(
        "", round(float(gross.sum()), 5), round(float(net.sum()), 5),
        round(per_trade_bps, 2), round(float(churn.mean()), 4),
        round(dd, 4), round(float(np.clip(sh, -5, 5)), 3),
        round(fill_rate, 4), int((churn > 0).sum()),
    )
