"""ReasonForge logic: evidence-forged synthesis over the 4 data domains.

Pipeline (all live, zero stubs):
  financial-data (DataRouter w/ badges) -> india-market aware symbol
  -> indicators.summarize + statistics_hub.describe
  -> scored verdict {BULLISH/BEARISH/NEUTRAL, confidence, reasons, risks}

Rules are transparent and test-covered (see tests/test_reasonforge.py):
- RSI>70 / <30, MACD hist sign, %B extremes, VWAP ±2σ, ADX trend,
  VaR99 guardrail, MaxDD guardrail.
- Confidence = capped mean of agreeing legs (0.35..0.85).
- Synthetic/STALE frames are LABELED in the verdict and force a
  confidence haircut + ` tradable:false` on SYNTH (never arm live size).

Also exposes `analyze(symbol)` returning the OpenCode evidence pack.
"""
from __future__ import annotations

from dataclasses import dataclass, field

REASONFORGE_VERSION = "reasonforge-v1"


@dataclass
class Verdict:
    symbol: str
    yahoo_symbol: str
    price: float
    stance: str  # BULLISH | BEARISH | NEUTRAL
    confidence: float
    score: float
    reasons: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    tier: str = ""
    badge: str = ""
    tradable: bool = False
    indicators: dict = field(default_factory=dict)
    statistics: dict = field(default_factory=dict)

    def render(self) -> str:
        badge = f" {self.badge}" if self.badge else ""
        lines = [
            f"{self.symbol} ${self.price:,.2f}{badge} [{self.tier}]",
            f"ReasonForge: {self.stance} conf {self.confidence:.0%} "
            f"(score {self.score:+.2f}) tradable={'YES' if self.tradable else 'NO'}",
            "Reasons: " + ("; ".join(self.reasons) or "none"),
            "Risks: " + ("; ".join(self.risks) or "none"),
        ]
        return "\n".join(lines)


def _score(ind: dict, stats: dict) -> tuple[float, list[str], list[str]]:
    reasons, risks = [], []
    score = 0.0
    # RSI mean-reversion leg
    rsi = float(ind.get("rsi_14", 50))
    if rsi > 70:
        score -= 1.0
        risks.append(f"RSI {rsi:.0f} overbought — chase risk")
    elif rsi < 30:
        score += 1.0
        reasons.append(f"RSI {rsi:.0f} oversold bounce setup")
    elif rsi > 55:
        score += 0.5
        reasons.append(f"RSI {rsi:.0f} bullish momentum")
    elif rsi < 45:
        score -= 0.5
        risks.append(f"RSI {rsi:.0f} soft momentum")
    # MACD trend leg
    hist = float(ind.get("macd_hist", 0))
    if hist > 0:
        score += 0.75
        reasons.append("MACD hist positive — trend up")
    else:
        score -= 0.75
        risks.append("MACD hist negative — trend down")
    # Bollinger extreme leg
    pctb = float(ind.get("boll_pct_b", 0.5))
    if pctb > 1.0:
        score -= 0.5
        risks.append("%B > 1 breakout-or-exhaustion")
    elif pctb < 0.0:
        score += 0.5
        reasons.append("%B < 0 washout leg")
    # VWAP location leg
    loc = float(ind.get("vwap_sigma", 0))
    if loc > 2.0:
        score -= 0.75
        risks.append(f"VWAP {loc:+.1f}s stretched — fade risk")
    elif loc < -2.0:
        score += 0.75
        reasons.append(f"VWAP {loc:+.1f}s dislocated — snapback")
    # ADX regime qualifier
    adx = float(ind.get("adx_14", 20))
    regime = ind.get("regime", "RANGING")
    if regime == "TRENDING":
        reasons.append(f"ADX {adx:.0f} trending — follow, don't fade")
    else:
        risks.append(f"ADX {adx:.0f} ranging — expect chop")
    # Statistics guardrails
    mdd = abs(float(stats.get("max_drawdown", 0)))
    if mdd > 0.30:
        risks.append(f"MaxDD {mdd:.0%} deep — size down")
        score *= 0.8
    var99 = abs(float(stats.get("var99_hist", 0)))
    if var99 > 0.08:
        risks.append(f"VaR99 {var99:.1%} fat tails — use stops")
    sharpe = float(stats.get("sharpe", 0))
    if sharpe > 1.0:
        score += 0.25
        reasons.append(f"Sharpe {sharpe:.2f} quality trend")
    elif sharpe < -0.5:
        score -= 0.25
    return score, reasons, risks


def analyze(symbol: str, days: int = 252, exchange: str = "AUTO") -> Verdict:
    """Full ReasonForge pass for one symbol (India-aware)."""
    from delta_os import india_market as IN
    from delta_os import indicators as TD
    from delta_os import statistics_hub as SH

    q = IN.quote(symbol, days=days, exchange=exchange)
    frame = q["frame"]
    ind = TD.summarize(frame)
    if "error" in ind:
        raise ValueError(ind["error"])
    stats = SH.describe(frame)
    if "error" in stats:
        raise ValueError(stats["error"])
    score, reasons, risks = _score(ind, stats)
    stance = "BULLISH" if score > 0.75 else ("BEARISH" if score < -0.75 else "NEUTRAL")
    # Confidence: base 0.5 + 0.07 per agreeing leg, capped; haircuts.
    legs = len(reasons) + len(risks)
    conf = min(0.85, 0.45 + 0.06 * legs + 0.05 * min(abs(score), 2.0))
    tier, badge = q["tier"], q["badge"]
    if badge == "[SYNTHETIC SIMULATION ONLY]":
        conf = min(conf, 0.40)
        risks.append("SYNTHETIC data — simulation only, not tradable")
        tradable = False
    elif badge == "[STALE DATA]":
        conf = min(conf, 0.55)
        risks.append("STALE data — verify fresh before sizing")
        tradable = False
    else:
        tradable = True
    return Verdict(symbol=symbol.strip().upper(), yahoo_symbol=q["yahoo_symbol"],
                   price=q["price"], stance=stance,
                   confidence=round(conf, 2), score=round(score, 2),
                   reasons=reasons, risks=risks, tier=tier, badge=badge,
                   tradable=tradable, indicators=ind, statistics=stats)


__all__ = ["REASONFORGE_VERSION", "Verdict", "analyze"]
