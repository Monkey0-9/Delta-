"""Statistics hub: one import for OpenCode + terminal + ReasonForge.

Aggregates (never forks):
- quant.time_series.statistics (returns, volatility, max_drawdown, ...)
- delta_os.quantkit (sharpe_maxdd, sortino_maxdd, var_cvar, beta_to_market)

`describe(frame, market=None)` returns the standard stats card used by
/stats, /quant and the ReasonForge evidence pack.
"""
from __future__ import annotations

import pandas as pd

STATISTICS_HUB_VERSION = "statistics-hub-v1"


def describe(frame: pd.DataFrame, market: pd.Series | None = None) -> dict:
    from delta_os import quantkit as Q
    from quant.time_series import statistics as S

    if frame is None or len(frame) < 30:
        return {"error": f"need >= 30 bars, have {0 if frame is None else len(frame)}."}
    closes = frame["close"].astype(float)
    rets = closes.pct_change().dropna()
    arith = S.arithmetic_returns(closes.tolist())
    vol_d = float(S.volatility(arith) if len(arith) else 0.0)
    ann_vol = float(S.annualized_volatility(arith) if len(arith) else 0.0)
    cum = float(S.cumulative_return(arith) if len(arith) else 0.0)
    mdd = float(S.max_drawdown(closes.tolist()))
    dd = float(S.downside_deviation(arith) if len(arith) else 0.0)
    sm = Q.sharpe_maxdd(closes)
    st = Q.sortino_maxdd(closes)
    vc95 = Q.var_cvar(rets, level=0.95)
    vc99 = Q.var_cvar(rets, level=0.99)
    out = {
        "n_bars": len(frame),
        "last": round(float(closes.iloc[-1]), 2),
        "cumulative_return": round(cum, 4),
        "daily_vol": round(vol_d, 4),
        "annualized_vol": round(ann_vol, 4),
        "downside_dev": round(dd, 4),
        "max_drawdown": round(mdd, 4),
        "sharpe": sm["sharpe"],
        "sortino": st["sortino"],
        "var95_hist": round(vc95["hist_var"], 4),
        "cvar95_hist": round(vc95["hist_cvar"], 4),
        "var99_hist": round(vc99["hist_var"], 4),
        "cvar99_hist": round(vc99["hist_cvar"], 4),
    }
    if market is not None:
        try:
            mkt_rets = market.astype(float).pct_change().dropna()
            out["beta_to_market"] = Q.beta_to_market(rets, mkt_rets)
        except Exception as exc:  # never break the card on beta
            out["beta_error"] = str(exc)[:120]
    return out


def render_card(symbol: str, stats: dict) -> str:
    if "error" in stats:
        return f"{symbol.upper()}: statistics {stats['error']}"
    beta = f" beta {stats['beta_to_market']}" if "beta_to_market" in stats else ""
    return (
        f"{symbol.upper()} ${stats['last']:,.2f} ({stats['n_bars']}d) | "
        f"cum {stats['cumulative_return']:+.2%} ann-vol {stats['annualized_vol']:.2%} "
        f"DD {stats['downside_dev']:.2%} MaxDD {stats['max_drawdown']:.2%}{beta} | "
        f"Sharpe {stats['sharpe']} Sortino {stats['sortino']} | "
        f"VaR95 {stats['var95_hist']:.2%} CVaR95 {stats['cvar95_hist']:.2%} "
        f"VaR99 {stats['var99_hist']:.2%}"
    )


__all__ = ["STATISTICS_HUB_VERSION", "describe", "render_card"]
