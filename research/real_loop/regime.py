"""W95 regime / world-model layer: vol, correlation, liquidity, risk-on/off."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

REGIME_VERSION = "regime-v2"


@dataclass(frozen=True, slots=True)
class RegimeState:
    volatility: str  # low|normal|high|extreme
    correlation: str  # low|normal|high
    liquidity: str  # deep|normal|thin
    risk_sentiment: str  # risk_on|neutral|risk_off
    label: str  # e.g. "high_vol_risk_off"
    confidence: float
    evidence: dict


def detect_regime(bars: dict[str, pd.DataFrame]) -> RegimeState:
    syms = list(bars)
    rets = pd.DataFrame({s: bars[s]["close"].astype(float).pct_change() for s in syms}).dropna()
    vols = pd.DataFrame({s: bars[s]["close"].astype(float).pct_change().rolling(20).std()
                         for s in syms}).dropna()
    if rets.empty or len(rets) < 30:
        return RegimeState("normal", "normal", "normal", "neutral", "neutral",
                           0.4, {"n": len(rets)})
    recent_vol = float(vols.iloc[-1].mean()) if not vols.empty else 0.015
    hist_vol = float(vols.mean().mean()) if not vols.empty else 0.015
    vratio = recent_vol / max(hist_vol, 1e-6)
    vol_state = "low" if vratio < 0.8 else ("normal" if vratio < 1.25
                                            else ("high" if vratio < 1.8 else "extreme"))
    corr = rets.tail(60).corr().values
    triu = corr[np.triu_indices_from(corr, 1)]
    avg_corr = float(np.nanmean(triu)) if triu.size else 0.0
    corr_state = "low" if avg_corr < 0.25 else ("normal" if avg_corr < 0.5 else "high")
    mom5 = float(rets.tail(20).mean().mean() * 20)
    liq_proxy = np.mean([float(bars[s]["volume"].tail(20).mean() /
                               max(bars[s]["volume"].tail(60).mean(), 1)) for s in syms])
    liq_state = "thin" if liq_proxy < 0.85 else ("deep" if liq_proxy > 1.15 else "normal")
    if vol_state in ("high", "extreme") and mom5 < -0.02:
        sent, label = "risk_off", f"{vol_state}_vol_risk_off"
    elif mom5 > 0.02 and vol_state in ("low", "normal"):
        sent, label = "risk_on", f"{vol_state}_vol_risk_on"
    else:
        sent, label = "neutral", f"{vol_state}_vol_neutral"
    conf = float(min(0.9, max(0.4, 0.5 + abs(avg_corr) * 0.3 + min(abs(mom5) * 5, 0.2))))
    return RegimeState(vol_state, corr_state, liq_state, sent, label, round(conf, 3),
                       {"vol_ratio": round(vratio, 3), "avg_corr": round(avg_corr, 3),
                        "mom_20d": round(mom5, 4), "liq_ratio": round(float(liq_proxy), 3)})
