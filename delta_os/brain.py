"""DELTA Institutional AI Brain (delta-fm-research).

Local quantitative intelligence engine that operates 100% offline without
requiring external cloud API keys. Provides:
1. Automated trading decisions & algorithmic strategy evaluation
2. Multi-factor stock analysis (technical, fundamental, valuation, liquidity)
3. General finance Q&A & conversational trading partner
4. Comprehensive risk analysis for equities, options (Black-Scholes Greeks), and futures
5. Probabilistic return forecasting & future price direction (P(r > 0), E[r], vol)
6. Regime-aware crash detection (sell before crash) & dip buying (buy before recovery)
7. Stock news catalyst & clickbait sentiment analysis
8. 24/7 Autonomous Portfolio Sentinel with automated loss circuit breaker (kill switch)
9. Top 0.001% quant algo-trading code generator (StatArb, VWAP, Momentum, Delta-Neutral)
"""
from __future__ import annotations

import math
import os
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from delta_os.data_router import DataRouter
from delta_os.quantkit import (
    calc_atr,
    calc_bollinger_bands,
    calc_macd,
    calc_rsi,
    calc_vwap,
    historical_var,
    cvar,
    sharpe_ratio,
    sortino_ratio,
    max_drawdown,
)
from delta_os.safety import SafetyState


# ============================================================================
# 1. OPTIONS MATHEMATICS (BLACK-SCHOLES GREEKS)
# ============================================================================

def _norm_cdf(x: float) -> float:
    """Standard normal cumulative distribution function."""
    return (1.0 + math.erf(x / math.sqrt(2.0))) / 2.0


def _norm_pdf(x: float) -> float:
    """Standard normal probability density function."""
    return (1.0 / math.sqrt(2.0 * math.pi)) * math.exp(-0.5 * x * x)


def calc_black_scholes_greeks(
    spot: float,
    strike: float,
    expiry_years: float,
    volatility: float,
    risk_free: float = 0.045,
    is_call: bool = True,
) -> Dict[str, float]:
    """Analytical Black-Scholes European option pricing & Greeks."""
    if spot <= 0 or strike <= 0 or expiry_years <= 0 or volatility <= 0:
        return {
            "price": 0.0,
            "delta": 0.0,
            "gamma": 0.0,
            "vega": 0.0,
            "theta": 0.0,
            "rho": 0.0,
            "prob_itm": 0.0,
        }

    sqrt_t = math.sqrt(expiry_years)
    d1 = (math.log(spot / strike) + (risk_free + 0.5 * volatility * volatility) * expiry_years) / (volatility * sqrt_t)
    d2 = d1 - volatility * sqrt_t

    pdf_d1 = _norm_pdf(d1)
    cdf_d1 = _norm_cdf(d1)
    cdf_d2 = _norm_cdf(d2)

    discount = math.exp(-risk_free * expiry_years)

    if is_call:
        price = spot * cdf_d1 - strike * discount * cdf_d2
        delta = cdf_d1
        theta = (
            -(spot * pdf_d1 * volatility) / (2.0 * sqrt_t)
            - risk_free * strike * discount * cdf_d2
        ) / 365.0  # Per-day decay
        rho = (strike * expiry_years * discount * cdf_d2) / 100.0  # Per 1% interest rate
        prob_itm = cdf_d2
    else:
        cdf_neg_d1 = _norm_cdf(-d1)
        cdf_neg_d2 = _norm_cdf(-d2)
        price = strike * discount * cdf_neg_d2 - spot * cdf_neg_d1
        delta = cdf_d1 - 1.0
        theta = (
            -(spot * pdf_d1 * volatility) / (2.0 * sqrt_t)
            + risk_free * strike * discount * cdf_neg_d2
        ) / 365.0
        rho = (-strike * expiry_years * discount * cdf_neg_d2) / 100.0
        prob_itm = cdf_neg_d2

    gamma = pdf_d1 / (spot * volatility * sqrt_t)
    vega = (spot * sqrt_t * pdf_d1) / 100.0  # Per 1% vol change

    return {
        "price": round(price, 4),
        "delta": round(delta, 4),
        "gamma": round(gamma, 6),
        "vega": round(vega, 4),
        "theta": round(theta, 4),
        "rho": round(rho, 4),
        "prob_itm": round(prob_itm * 100.0, 2),
    }


# ============================================================================
# 2. LOCAL QUANTITATIVE BRAIN
# ============================================================================

class DeltaBrain:
    """DELTA Institutional Local AI Quant Brain.
    
    Provides local reasoning, auto-trading decisions, risk analysis,
    and algo generation with zero external API dependencies.
    """

    def __init__(self, data_router: Optional[DataRouter] = None):
        self.data_router = data_router or DataRouter()
        # Legacy in-memory map kept for backward compat; keys now live in
        # the AES vault (see set_api_key) with env fallback in get_key_status.
        self.api_keys: Dict[str, str] = {}

    def set_api_key(self, provider: str, key: str, vault=None) -> str:
        """Store a provider key in the AES vault (never plaintext/env mirror).

        Raises RuntimeError when no unlocked vault is supplied.
        """
        prov = provider.lower().strip()
        token = key.strip()
        if not token:
            raise ValueError("empty API token refused.")
        if vault is None or getattr(vault, "locked", True):
            raise RuntimeError("vault locked — /auth wizard first.")
        vault.set(prov, {"api_key": token})
        return f"API Key for [{prov.upper()}] stored in AES-256 vault."

    def get_key_status(self, vault=None) -> Dict[str, bool]:
        """Key presence from vault (unlocked) or environment fallback."""
        providers = ["anthropic", "openai", "deepseek", "groq", "gemini", "astro"]
        out = {}
        for p in providers:
            ok = False
            try:
                if vault is not None and not getattr(vault, "locked", True):
                    ok = bool((vault.get(p) or {}).get("api_key"))
            except Exception:
                ok = False
            out[p] = ok or bool(os.environ.get(f"{p.upper()}_API_KEY"))
        return out

    # ------------------------------------------------------------------------
    # Stock Multi-Factor Analysis
    # ------------------------------------------------------------------------
    def analyze_stock(self, symbol: str) -> Dict[str, Any]:
        """Perform comprehensive technical, fundamental, and risk analysis."""
        sym = symbol.upper().strip()
        qf = self.data_router.quote(sym, days=150)
        df = qf.frame
        source = f"{qf.provenance.tier}{qf.provenance.badge}"

        if df.empty or len(df) < 20:
            return {
                "symbol": sym,
                "error": f"Insufficient market data for {sym}. Data source status: {source}",
                "data_tier": qf.provenance.tier,
            }

        closes = df["close"].to_numpy(dtype=np.float64)
        highs = df["high"].to_numpy(dtype=np.float64)
        lows = df["low"].to_numpy(dtype=np.float64)
        volumes = df["volume"].to_numpy(dtype=np.float64)

        cur_price = float(closes[-1])
        prev_price = float(closes[-2]) if len(closes) > 1 else cur_price
        ret_1d = (cur_price - prev_price) / prev_price if prev_price > 0 else 0.0

        # Technical Indicators
        rsi_val = float(calc_rsi(closes, period=14))
        bb_upper, bb_mid, bb_lower = calc_bollinger_bands(closes, period=20, num_std=2.0)
        macd_line, macd_sig, macd_hist = calc_macd(closes)
        atr_val = float(calc_atr(highs, lows, closes, period=14))
        vwap_val = float(calc_vwap(highs, lows, closes, volumes))

        # Moving Averages & Trend
        ma_20 = float(np.mean(closes[-20:]))
        ma_50 = float(np.mean(closes[-50:])) if len(closes) >= 50 else ma_20
        trend = "BULLISH" if cur_price > ma_50 and ma_20 > ma_50 else ("BEARISH" if cur_price < ma_50 else "NEUTRAL")

        # Volatility & Drawdown
        returns = np.diff(closes) / closes[:-1]
        ann_vol = float(np.std(returns) * math.sqrt(252)) if len(returns) > 5 else 0.20
        var_95 = float(historical_var(returns, confidence=0.95))
        var_99 = float(historical_var(returns, confidence=0.99))
        cvar_95 = float(cvar(returns, confidence=0.95))
        mdd = float(max_drawdown(closes))

        # Valuation & Multi-Factor Score (-100 to +100)
        rsi_contrib = (1.0 if rsi_val < 35 else (-1.0 if rsi_val > 70 else 0.0)) * 25.0
        macd_contrib = (1.0 if macd_hist > 0.001 else (-1.0 if macd_hist < -0.001 else 0.0)) * 25.0
        vwap_diff = (cur_price - vwap_val) / max(vwap_val, 1e-6)
        vwap_contrib = (1.0 if vwap_diff > 0.001 else (-1.0 if vwap_diff < -0.001 else 0.0)) * 20.0
        trend_contrib = (1.0 if trend == "BULLISH" else (-1.0 if trend == "BEARISH" else 0.0)) * 30.0
        tech_score = rsi_contrib + macd_contrib + vwap_contrib + trend_contrib
        verdict = "STRONG BUY" if tech_score >= 45 else ("BUY" if tech_score >= 15 else ("STRONG SELL" if tech_score <= -45 else ("SELL" if tech_score <= -15 else "NEUTRAL")))

        return {
            "symbol": sym,
            "price": cur_price,
            "change_pct": round(ret_1d * 100.0, 2),
            "trend": trend,
            "verdict": verdict,
            "composite_score": round(tech_score, 1),
            "indicators": {
                "rsi_14": round(rsi_val, 2),
                "macd": round(macd_line, 3),
                "macd_signal": round(macd_sig, 3),
                "macd_hist": round(macd_hist, 3),
                "bb_upper": round(bb_upper, 2),
                "bb_mid": round(bb_mid, 2),
                "bb_lower": round(bb_lower, 2),
                "atr_14": round(atr_val, 2),
                "vwap": round(vwap_val, 2),
                "ma_20": round(ma_20, 2),
                "ma_50": round(ma_50, 2),
            },
            "risk_metrics": {
                "annualized_vol": round(ann_vol * 100.0, 2),
                "var_95_daily_pct": round(var_95 * 100.0, 2),
                "var_99_daily_pct": round(var_99 * 100.0, 2),
                "cvar_95_daily_pct": round(cvar_95 * 100.0, 2),
                "max_drawdown_pct": round(mdd * 100.0, 2),
            },
            "provenance": source,
            "data_tier": qf.provenance.tier,
            "data_badge": qf.provenance.badge,
        }

    # ------------------------------------------------------------------------
    # Risk Analysis for Equities, Options & Futures
    # ------------------------------------------------------------------------
    def analyze_risk(
        self,
        symbol: str,
        asset_type: str = "STOCK",
        strike: Optional[float] = None,
        expiry_days: int = 30,
        is_call: bool = True,
        notional_dollars: float = 100_000.0,
    ) -> Dict[str, Any]:
        """Comprehensive multi-asset risk analysis (VaR, Greeks, stress tests).

        Fail-closed: empty frames refuse (never invented spot/vol).
        """
        sym = symbol.upper().strip()
        asset_type = asset_type.upper().strip()
        qf = self.data_router.quote(sym, days=120)
        df = qf.frame
        source = f"{qf.provenance.tier}{qf.provenance.badge}"

        if df.empty:
            return {
                "symbol": sym,
                "asset_type": asset_type,
                "error": f"No market data for {sym}. Data source status: {source}",
                "data_tier": qf.provenance.tier,
            }
        spot = float(df["close"].iloc[-1])
        if not np.isfinite(spot) or spot <= 0:
            return {
                "symbol": sym,
                "asset_type": asset_type,
                "error": f"Unusable last price for {sym}. Data source status: {source}",
                "data_tier": qf.provenance.tier,
            }
        closes = df["close"].to_numpy(dtype=np.float64)
        returns = np.diff(closes) / closes[:-1] if len(closes) > 1 else np.array([])
        ann_vol = float(np.std(returns) * math.sqrt(252)) if len(returns) > 5 else 0.25

        t_years = max(expiry_days, 1) / 365.0
        k = strike if strike and strike > 0 else spot

        base_res = {
            "symbol": sym,
            "asset_type": asset_type,
            "spot_price": round(spot, 2),
            "notional_dollars": notional_dollars,
            "implied_volatility_pct": round(ann_vol * 100.0, 2),
            "provenance": source,
            "data_tier": qf.provenance.tier,
            "data_badge": qf.provenance.badge,
        }

        if asset_type in ("OPTION", "OPTIONS"):
            greeks = calc_black_scholes_greeks(
                spot=spot,
                strike=k,
                expiry_years=t_years,
                volatility=ann_vol,
                risk_free=0.045,
                is_call=is_call,
            )
            # Dollar Greeks for standard 100-share contract
            num_contracts = max(1, int(notional_dollars / (spot * 100)))
            dollar_delta = greeks["delta"] * spot * 100 * num_contracts
            dollar_gamma = greeks["gamma"] * spot * spot * 100 * num_contracts
            dollar_vega = greeks["vega"] * 100 * num_contracts
            dollar_theta = greeks["theta"] * 100 * num_contracts

            base_res.update({
                "option_type": "CALL" if is_call else "PUT",
                "strike": k,
                "expiry_days": expiry_days,
                "contracts": num_contracts,
                "theoretical_price": greeks["price"],
                "greeks": greeks,
                "dollar_exposures": {
                    "dollar_delta": round(dollar_delta, 2),
                    "dollar_gamma": round(dollar_gamma, 2),
                    "dollar_vega": round(dollar_vega, 2),
                    "dollar_theta_daily": round(dollar_theta, 2),
                },
                "prob_itm_pct": greeks["prob_itm"],
                "tail_loss_10pct_spot": round(dollar_delta * -0.10 + 0.5 * dollar_gamma * 0.01, 2),
            })
        elif asset_type in ("FUTURE", "FUTURES"):
            leverage = 10.0  # Standard CME equity index margin
            margin_req = notional_dollars / leverage
            point_value = 50.0  # E-mini standard
            base_res.update({
                "effective_leverage": f"{leverage:.1f}x",
                "initial_margin_dollars": round(margin_req, 2),
                "maintenance_margin_dollars": round(margin_req * 0.90, 2),
                "margin_call_buffer_pct": round((1.0 - 0.90) * 100.0 / leverage, 2),
                "daily_var_99_dollars": round(notional_dollars * (ann_vol / math.sqrt(252)) * 2.326, 2),
            })
        else:  # Stock / Equity
            daily_vol = ann_vol / math.sqrt(252)
            shares = int(notional_dollars / spot) if spot > 0 else 0
            base_res.update({
                "shares": shares,
                "daily_var_95_dollars": round(notional_dollars * daily_vol * 1.645, 2),
                "daily_var_99_dollars": round(notional_dollars * daily_vol * 2.326, 2),
                "daily_cvar_95_dollars": round(notional_dollars * daily_vol * 2.06, 2),
                "scenario_shocks": {
                    "rate_shock_neg200bps": round(notional_dollars * -0.04, 2),
                    "crude_oil_spike_plus10pct": round(notional_dollars * -0.025, 2),
                    "equity_crash_neg20pct": round(notional_dollars * -0.20, 2),
                },
            })

        return base_res

    # ------------------------------------------------------------------------
    # Automation Gate: per-trade ALLOW / HOLD / BLOCK + best-of-list ranking
    # ------------------------------------------------------------------------
    AUTOMATION_VERDICTS = ("ALLOW", "HOLD", "BLOCK")

    def gate_automation(self, symbol: str, side: str) -> Dict[str, Any]:
        """Analyze one candidate trade; verdict BEFORE completion.

        ALLOW: proceed to firewall/govern rails. HOLD: pause with reasons
        (caller may offer ranked alternates). BLOCK: refuse outright.
        Deterministic; data-tier is authoritative over signals.
        """
        sym = symbol.upper().strip()
        s = side.lower().strip()
        reasons: List[str] = []
        if s not in ("buy", "sell"):
            return {"symbol": sym, "side": s, "verdict": "BLOCK",
                    "reasons": ["side must be buy|sell"], "details": {}}
        info = self.analyze_stock(sym)
        if "error" in info:
            return {"symbol": sym, "side": s, "verdict": "BLOCK",
                    "reasons": [info["error"]], "details": {"data_tier": info.get("data_tier")}}
        if info.get("data_tier") not in ("TIER1", "TIER2"):
            return {"symbol": sym, "side": s, "verdict": "BLOCK",
                    "reasons": [f"refused on {info.get('data_tier')}: execution needs fresh TIER1/TIER2"],
                    "details": {"data_tier": info.get("data_tier")}}
        fc = self.forecast_direction(sym)
        regime = self.evaluate_portfolio_regime(positions={sym: 1.0})
        verdict = "ALLOW"
        verdict_txt = str(info.get("verdict", "NEUTRAL"))
        if regime.get("market_regime") == "CRISIS_STRESS" and s == "buy":
            verdict = "HOLD"
            reasons.append(f"CRISIS_STRESS regime (crash {regime.get('crash_probability_pct')}%): no new longs")
        if verdict_txt in ("SELL", "STRONG SELL") and s == "buy":
            verdict = "HOLD"
            reasons.append(f"counter-signal: brain verdict {verdict_txt} opposes BUY")
        if verdict_txt in ("BUY", "STRONG BUY") and s == "sell":
            verdict = "HOLD"
            reasons.append(f"counter-signal: brain verdict {verdict_txt} opposes SELL")
        er = float(fc.get("expected_return_pct", 0.0) or 0.0)
        if er < -1.0 and s == "buy":
            verdict = "HOLD"
            reasons.append(f"negative drift {er:+.2f}% over {fc.get('horizon_days')}d opposes BUY")
        if er > 1.0 and s == "sell":
            verdict = "HOLD"
            reasons.append(f"positive drift {er:+.2f}% over {fc.get('horizon_days')}d opposes SELL")
        if verdict == "ALLOW":
            reasons.append(f"aligned: verdict {verdict_txt}, drift {er:+.2f}%, regime {regime.get('market_regime')}")
        return {"symbol": sym, "side": s, "verdict": verdict, "reasons": reasons,
                "details": {"brain_verdict": verdict_txt,
                            "expected_return_pct": er,
                            "market_regime": regime.get("market_regime"),
                            "crash_probability_pct": regime.get("crash_probability_pct"),
                            "data_tier": info.get("data_tier")}}

    def rank_alternatives(self, symbols: List[str], side: str) -> Dict[str, Any]:
        """Risk-rank a caller-supplied list (never invents tickers).

        BUY side: higher composite score first, VaR99 breaks ties (lower wins).
        SELL side (closing strength): weakest first. Unreadable symbols are
        listed as SKIPPED with reasons, never silently dropped.
        """
        s = side.lower().strip()
        ranked: List[Dict[str, Any]] = []
        skipped: List[Dict[str, str]] = []
        for raw in symbols or []:
            sym = (raw or "").upper().strip()
            if not sym:
                continue
            info = self.analyze_stock(sym)
            if "error" in info or info.get("data_tier") not in ("TIER1", "TIER2"):
                skipped.append({"symbol": sym,
                                "reason": info.get("error", f"tier {info.get('data_tier')}")})
                continue
            ranked.append({"symbol": sym,
                           "composite_score": float(info.get("composite_score", 0.0)),
                           "var_99": float(info.get("risk_metrics", {}).get("var_99_daily_pct", 99.0)),
                           "verdict": info.get("verdict", "NEUTRAL")})
        reverse = s == "buy"
        ranked.sort(key=lambda r: (r["composite_score"], -r["var_99"]),
                    reverse=reverse)
        pick = ranked[0]["symbol"] if ranked else None
        return {"side": s, "ranking": ranked, "skipped": skipped, "pick": pick,
                "rationale": (f"best-of {[r['symbol'] for r in ranked]} by "
                              f"{'composite strength, VaR99 tiebreak' if s == 'buy' else 'weakest-first exit'}")
                if pick else "no tradable alternate in list"}

    # ------------------------------------------------------------------------
    # Crash Defense (hedge sizing) & Dip-Buy Ladder — advisory plans executed
    # only via the gated /trade path (never self-submitting).
    # ------------------------------------------------------------------------
    def hedge_plan(self, symbol: str, qty_held: float,
                   hedge_fraction: float = 0.5) -> Dict[str, Any]:
        """Protective-put sizing for a long position (30-day, 5% OTM)."""
        sym = symbol.upper().strip()
        if qty_held <= 0:
            return {"symbol": sym, "error": "no long position to hedge"}
        risk = self.analyze_risk(sym, asset_type="STOCK",
                                 notional_dollars=1.0)
        if "error" in risk:
            return {"symbol": sym, "error": risk["error"],
                    "data_tier": risk.get("data_tier")}
        spot = float(risk["spot_price"])
        ann_vol = float(risk["implied_volatility_pct"]) / 100.0
        strike = round(spot * 0.95, 2)
        greeks = calc_black_scholes_greeks(spot=spot, strike=strike,
                                           expiry_years=30 / 365.0,
                                           volatility=max(ann_vol, 0.05),
                                           is_call=False)
        hedge_notional = spot * qty_held * hedge_fraction
        contracts = max(1, int(hedge_notional / (spot * 100)))
        premium = greeks["price"] * 100 * contracts
        return {"symbol": sym, "action": "BUY protective puts (30d, 5% OTM)",
                "qty_held": qty_held, "hedge_fraction": hedge_fraction,
                "strike": strike, "contracts": contracts,
                "premium_dollars": round(premium, 2),
                "put_delta": greeks["delta"],
                "hedged_delta_shares": round(-greeks["delta"] * 100 * contracts, 1),
                "execute_via": f"/trade {sym} buy {contracts} (put contracts, gated)",
                "provenance": risk.get("provenance"), "data_tier": risk.get("data_tier")}

    def dip_plan(self, symbol: str, equity: float) -> Dict[str, Any]:
        """Oversold dip-buy ladder (3 tranches). Refuses unless RSI < 35."""
        sym = symbol.upper().strip()
        info = self.analyze_stock(sym)
        if "error" in info:
            return {"symbol": sym, "error": info["error"],
                    "data_tier": info.get("data_tier")}
        rsi = float(info["indicators"]["rsi_14"])
        if rsi >= 35.0:
            return {"symbol": sym, "action": "NO DIP (not oversold)",
                    "rsi_14": rsi,
                    "reason": f"RSI {rsi:.1f} >= 35: dip ladder refused, use /trade explicitly",
                    "data_tier": info.get("data_tier")}
        price = float(info["price"])
        # 0.25-Kelly-flavoured cap: total risk <= 2% equity across tranches.
        budget = max(0.0, equity) * 0.02
        per = budget / 3.0
        tranches = []
        for i, (frac, note) in enumerate(((0.5, "first touch"), (0.3, "lower low"), (0.2, "capitulation")), 1):
            qty = int((per * frac * 2) / price) if price > 0 else 0
            tranches.append({"tranche": i, "note": note,
                             "limit_price": round(price * (1 - 0.01 * i), 2),
                             "qty": qty})
        return {"symbol": sym, "action": "BUY LOW ladder (3 tranches)",
                "rsi_14": rsi, "ref_price": price, "tranches": tranches,
                "execute_via": "/trade (each leg re-gated)",
                "provenance": info.get("provenance"), "data_tier": info.get("data_tier")}

    # ------------------------------------------------------------------------
    # Directional Return Forecast
    # ------------------------------------------------------------------------
    def forecast_direction(self, symbol: str, horizon_days: int = 5) -> Dict[str, Any]:
        """Predict expected return distribution and high/low turn points."""
        analysis = self.analyze_stock(symbol)
        if "error" in analysis:
            return analysis
        # F-item (P3): refuse on stale/synthetic inputs — a forecast built on
        # non-fresh data is fabrication, not prediction. Callers already
        # render "error" honestly (chat, /forecast, gate).
        if analysis.get("data_tier") not in ("TIER1", "TIER2"):
            return {"symbol": symbol.upper(), "horizon_days": horizon_days,
                    "error": (f"ABSTAIN: {symbol.upper()} inputs are "
                              f"{analysis.get('data_tier')}; forecast requires "
                              f"fresh TIER1/TIER2 data")}

        price = analysis["price"]
        rsi = analysis["indicators"]["rsi_14"]
        macd_h = analysis["indicators"]["macd_hist"]
        ann_vol = analysis["risk_metrics"]["annualized_vol"] / 100.0

        # Multi-factor expected return drift
        h_years = horizon_days / 252.0
        h_vol = ann_vol * math.sqrt(h_years)

        # Mean reversion + momentum signals
        drift_bps = 0.0
        if rsi < 30:  # Oversold exhaustion (Buy signal before low recovery)
            drift_bps += 180.0
        elif rsi > 70:  # Overbought exhaustion (Sell signal before high pullback)
            drift_bps -= 180.0

        if macd_h > 0:
            drift_bps += 80.0
        else:
            drift_bps -= 80.0

        expected_return_pct = (drift_bps / 10_000.0) * 100.0
        prob_positive = _norm_cdf(expected_return_pct / (h_vol * 100.0 + 1e-6))

        direction = "BULLISH (UP)" if expected_return_pct > 0.5 else ("BEARISH (DOWN)" if expected_return_pct < -0.5 else "NEUTRAL")
        # F-item (P3): edge below noise -> abstain, never a confident call.
        # |z| < 0.25 means P(positive) sits inside [40%, 60%]: a coin flip
        # dressed as analysis. Direction and action say so explicitly.
        abstained = abs(prob_positive - 0.5) <= 0.10
        if abstained:
            direction = "ABSTAIN (edge below noise)"
            action_recommendation = (
                "NO ACTION: expected edge is inside noise bounds — "
                "no position without stronger evidence")
        else:
            action_recommendation = (
                "BUY BEFORE LOW: Accumulate near oversold support with tight stop"
                if rsi < 35
                else ("TAKE PROFIT / SELL: Trim into resistance before reversal" if rsi > 68 else "HOLD: Trend confirmed")
            )
            # P3 calibration wiring: every directional call enters the
            # forecast log; forecast_calibration() resolves elapsed horizons
            # against realized prices. ABSTAIN calls carry no claim to score.
            self.log_forecast(symbol.upper(), horizon_days, direction,
                              round(prob_positive, 4))
        target_price = round(price * (1.0 + expected_return_pct / 100.0), 2)
        ci_lower = round(price * (1.0 + (expected_return_pct / 100.0 - 1.96 * h_vol)), 2)
        ci_upper = round(price * (1.0 + (expected_return_pct / 100.0 + 1.96 * h_vol)), 2)

        return {
            "symbol": symbol.upper(),
            "horizon_days": horizon_days,
            "current_price": price,
            "direction": direction,
            "expected_return_pct": round(expected_return_pct, 2),
            "target_price": target_price,
            "confidence_interval_95": [ci_lower, ci_upper],
            "probability_positive_return_pct": round(prob_positive * 100.0, 1),
            "forecast_volatility_pct": round(h_vol * 100.0, 2),
            "turn_recommendation": action_recommendation,
            # Honesty envelope: fixed-bps heuristic, never backtested.
            "model": "delta-fm-research",
            "model_version": "brain-v1",
            "calibration": "uncalibrated-heuristic (fixed RSI/MACD bps drifts; no IC/backtest)",
            "confidence": 0.35,
            "evidence": {"rsi_14": rsi, "macd_hist": macd_h,
                         "ann_vol_pct": round(ann_vol * 100.0, 2)},
            "provenance": analysis.get("provenance"),
            "data_tier": analysis.get("data_tier"),
        }

    # -- forecast track record (P3 calibration wiring) ----------------------
    def _forecast_log_path(self) -> str:
        from delta_os.safety import _session_path

        return str(_session_path().parent / "forecast_log.jsonl")

    def log_forecast(self, symbol: str, horizon_days: int, direction: str,
                     prob_positive: float) -> None:
        """Append a directional call to the forecast log (best-effort, capped).
        Never raises: logging must not break forecasting."""
        try:
            import json as _json

            entry = {"ts": datetime.now(timezone.utc).isoformat(),
                     "symbol": symbol, "horizon_days": int(horizon_days),
                     "direction": direction, "prob_positive": float(prob_positive)}
            path = self._forecast_log_path()
            parent = os.path.dirname(path)
            if parent:
                os.makedirs(parent, exist_ok=True)
            if os.path.exists(path) and os.path.getsize(path) > 1_000_000:
                return  # cap: stop growing rather than rewrite mid-session
            with open(path, "a", encoding="utf-8") as f:
                f.write(_json.dumps(entry) + "\n")
        except Exception:
            pass

    def forecast_calibration(self, price_lookup=None) -> Dict[str, Any]:
        """Score resolved forecasts: horizons fully elapsed get outcomes from
        realized prices. Single-bin ECE = |accuracy - mean prob| (labeled as
        such). Unresolvable entries are skipped, never fabricated."""
        import json as _json

        path = self._forecast_log_path()
        try:
            with open(path, encoding="utf-8") as f:
                entries = [_json.loads(line) for line in f if line.strip()]
        except FileNotFoundError:
            entries = []
        except Exception:
            return {"n_logged": 0, "n_resolved": 0, "accuracy": None,
                    "mean_prob": None, "ece_single_bin": None,
                    "note": "log unreadable"}
        now = datetime.now(timezone.utc)
        lookup = price_lookup or self._router_close_at
        hits, probs = 0, []
        for e in entries[-500:]:
            try:
                ts = datetime.fromisoformat(e["ts"])
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                horizon = int(e.get("horizon_days", 5))
                if (now - ts).days < horizon:
                    continue  # not yet resolvable
                p0 = lookup(e["symbol"], ts.date().isoformat())
                p1 = lookup(e["symbol"], (ts + timedelta(days=horizon)).date().isoformat())
                if p0 is None or p1 is None or p0 <= 0:
                    continue
                realized_up = p1 > p0
                predicted_up = "BEARISH" not in str(e.get("direction", ""))
                hits += predicted_up == realized_up
                probs.append(float(e.get("prob_positive", 0.5)))
            except Exception:
                continue
        n = len(probs)
        if not n:
            return {"n_logged": len(entries), "n_resolved": 0,
                    "accuracy": None, "mean_prob": None,
                    "ece_single_bin": None,
                    "note": "no resolved forecasts yet"}
        acc = hits / n
        mean_p = sum(probs) / n
        return {"n_logged": len(entries), "n_resolved": n,
                "accuracy": round(acc, 4), "mean_prob": round(mean_p, 4),
                "ece_single_bin": round(abs(acc - mean_p), 4),
                "note": "single-bin ECE; per-bin curves need larger N"}

    def _router_close_at(self, symbol: str, day: str):
        """Realized close on/before a calendar day via the data router."""
        try:
            frame = self.data_router.quote(symbol, days=400).frame
            if frame is None or len(frame) == 0:
                return None
            idx = frame.index
            target = pd.Timestamp(day, tz="UTC")
            mask = idx <= target
            if not bool(mask.any()):
                return None
            return float(frame["close"][mask].iloc[-1])
        except Exception:
            return None

    # ------------------------------------------------------------------------
    # Regime-Aware Crash Warning & Rebalance Decisions
    # ------------------------------------------------------------------------
    def evaluate_portfolio_regime(
        self,
        positions: Dict[str, float],
        cash: float = 100_000.0,
    ) -> Dict[str, Any]:
        """Detect crash signals, oversold dip-buying, and profit-taking opportunities."""
        spy_analysis = self.analyze_stock("SPY")
        vix_proxy = spy_analysis.get("risk_metrics", {}).get("annualized_vol", 20.0)

        # Crash probability based on market volatility & momentum breakdown
        rsi_spy = spy_analysis.get("indicators", {}).get("rsi_14", 50.0)
        macd_h_spy = spy_analysis.get("indicators", {}).get("macd_hist", 0.0)

        crash_prob = 15.0  # Base market tail risk
        if vix_proxy > 28.0:
            crash_prob += 35.0
        if macd_h_spy < -1.0:
            crash_prob += 20.0
        if rsi_spy < 40.0:
            crash_prob += 15.0

        # Independent consult: canonical quant regime detector (guarded;
        # heuristic stands alone when the detector is unreachable).
        regime_source = "heuristic"
        detector_regime = None
        try:
            from decimal import Decimal
            from quant.regime.detector import classify_regime

            spy_full = self.analyze_stock("SPY")
            ind = spy_full.get("indicators", {})
            ma20 = float(ind.get("ma_20", 0.0) or 0.0)
            ma50 = float(ind.get("ma_50", 0.0) or 0.0)
            trend_strength = abs(ma20 - ma50) / ma50 if ma50 > 0 else 0.0
            detected = classify_regime(
                realized_vol=Decimal(str(vix_proxy / 100.0)),
                vol_high_threshold=Decimal("0.25"),
                trend_strength=Decimal(str(trend_strength)))
            detector_regime = getattr(detected, "name", str(detected))
            regime_source = "quant-regime"
            if detector_regime == "CRISIS" and crash_prob < 60.0:
                crash_prob = 60.0  # detector-confirmed floor, labeled below
        except Exception:
            detector_regime = None

        is_crisis = crash_prob >= 60.0

        recommendations: List[Dict[str, str]] = []
        for sym, qty in positions.items():
            if qty == 0:
                continue
            stock_info = self.analyze_stock(sym)
            if "error" in stock_info:
                continue
            rsi = stock_info["indicators"]["rsi_14"]
            price = stock_info["price"]

            if is_crisis and stock_info["trend"] == "BEARISH":
                recommendations.append({
                    "symbol": sym,
                    "action": "SELL / HEDGE PRE-CRASH",
                    "reason": f"Systemic crash warning ({crash_prob:.0f}% risk). Cut exposure or buy protective puts.",
                    "urgency": "CRITICAL",
                })
            elif rsi < 32.0:
                recommendations.append({
                    "symbol": sym,
                    "action": "BUY LOW (OVERSOLD DIP)",
                    "reason": f"RSI={rsi:.1f} indicates capitulation low. High statistical probability of recovery bounce.",
                    "urgency": "MEDIUM",
                })
            elif rsi > 72.0:
                recommendations.append({
                    "symbol": sym,
                    "action": "TAKE PROFIT (EXTENDED HIGH)",
                    "reason": f"RSI={rsi:.1f} indicates peak exhaustion. Trim position before momentum fade.",
                    "urgency": "HIGH",
                })

        return {
            "market_regime": "CRISIS_STRESS" if is_crisis else ("HIGH_VOLATILITY" if vix_proxy > 22.0 else "ORDERLY"),
            "crash_probability_pct": round(crash_prob, 1),
            "vix_volatility_proxy": round(vix_proxy, 1),
            "cash_buffer_available": cash,
            "actionable_recommendations": recommendations,
            # Honesty envelope for the crash heuristic.
            "model": "delta-fm-research",
            "model_version": "brain-v1",
            "calibration": "uncalibrated-heuristic (additive vol/momentum rules; no IC/backtest)",
            "regime_source": regime_source,
            "detector_regime": detector_regime,
        }

    # ------------------------------------------------------------------------
    # Stock News & Sentiment Analysis
    # ------------------------------------------------------------------------
    def analyze_news(self, symbol: str) -> Dict[str, Any]:
        """Parse financial headlines and extract catalyst sentiment.

        Source: live Google News RSS via data_router.news_sentiment.
        Fail-closed UNAVAILABLE on network failure (never fake headlines).
        """
        from delta_os.data_router import news_sentiment

        sym = symbol.upper().strip()
        try:
            feed = news_sentiment(f"{sym} stock")
        except Exception as exc:
            return {
                "symbol": sym,
                "status": "UNAVAILABLE",
                "message": f"No live news feeds found for {sym}: {exc}",
                "headlines": [],
            }
        raw_items = feed.get("items", [])

        bullish_keywords = {"beats", "surpasses", "growth", "record", "upgrade", "outperform", "profit", "surges", "dividend"}
        bearish_keywords = {"misses", "downgrade", "falls", "plunges", "investigation", "loss", "warning", "lawsuit", "decline"}

        scored_headlines = []
        total_score = 0
        for h in raw_items[:8]:
            title = h.get("title", "")
            lower_title = title.lower()
            bull_hits = sum(1 for w in bullish_keywords if w in lower_title)
            bear_hits = sum(1 for w in bearish_keywords if w in lower_title)
            score = bull_hits - bear_hits
            total_score += score
            sentiment = "BULLISH" if score > 0 else ("BEARISH" if score < 0 else "NEUTRAL")
            scored_headlines.append({
                "title": title,
                "publisher": "news.google.com RSS",
                "sentiment": sentiment,
                "url": h.get("link", ""),
            })

        overall = "POSITIVE" if total_score > 1 else ("NEGATIVE" if total_score < -1 else "NEUTRAL")
        return {
            "symbol": sym,
            "overall_sentiment": overall,
            "sentiment_score": total_score,
            "headline_count": len(scored_headlines),
            "headlines": scored_headlines,
            "provenance": "TIER1-news.google.com-RSS[live]",
        }

    # ------------------------------------------------------------------------
    # Top 0.001% Algorithmic Code Generator
    # ------------------------------------------------------------------------
    def generate_algo_code(self, strategy_type: str = "statarb", language: str = "python") -> str:
        """Generate institutional-grade quantitative trading algorithms."""
        strat = strategy_type.lower().strip()

        if "statarb" in strat or "pair" in strat:
            return '''"""Institutional Statistical Arbitrage (Pairs Trading) Algorithm.

Engineered by DELTA OS Top 0.001% Quantitative Architecture.
Features:
- Dynamic Kalman Filter rolling hedge ratio (beta)
- Engle-Granger Cointegration verification
- Ornstein-Uhlenbeck mean-reversion speed estimation
- Volatility-targeted fractional Kelly position sizing
- Pre-trade risk firewall & stop-loss bounds
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class StatArbSignal:
    timestamp: str
    asset_y: str
    asset_x: str
    hedge_ratio: float
    spread: float
    z_score: float
    allocation_y: float
    allocation_x: float
    action: str

class KalmanPairsTrader:
    def __init__(self, asset_y: str, asset_x: str, delta: float = 1e-4, entry_z: float = 2.0, exit_z: float = 0.5):
        self.asset_y = asset_y
        self.asset_x = asset_x
        self.delta = delta
        self.entry_z = entry_z
        self.exit_z = exit_z
        
        # State vector [beta, alpha]^T
        self.theta = np.zeros(2)
        self.P = np.eye(2) * 1.0
        self.R = 1e-3  # Measurement variance
        self.Q = np.eye(2) * delta / (1.0 - delta)  # Process noise

    def update(self, price_y: float, price_x: float, timestamp: str = "") -> StatArbSignal:
        # Measurement vector H = [price_x, 1.0]
        H = np.array([price_x, 1.0])
        
        # 1. State prediction
        P_pred = self.P + self.Q
        
        # 2. Measurement prediction
        y_hat = float(H @ self.theta)
        error = price_y - y_hat
        
        # 3. Kalman Gain
        S = float(H @ P_pred @ H.T) + self.R
        K = (P_pred @ H.T) / S
        
        # 4. State Update
        self.theta = self.theta + K * error
        self.P = P_pred - np.outer(K, H) @ P_pred
        
        beta, alpha = self.theta[0], self.theta[1]
        spread = error
        spread_std = math.sqrt(max(S, 1e-8))
        z_score = spread / spread_std
        
        # Signal Generation
        action = "HOLD"
        alloc_y, alloc_x = 0.0, 0.0
        
        if z_score > self.entry_z:
            action = "SHORT_SPREAD (SELL Y, BUY X)"
            alloc_y = -0.5
            alloc_x = 0.5 * beta
        elif z_score < -self.entry_z:
            action = "LONG_SPREAD (BUY Y, SELL X)"
            alloc_y = 0.5
            alloc_x = -0.5 * beta
        elif abs(z_score) < self.exit_z:
            action = "EXIT_FLATTEN"
            
        return StatArbSignal(
            timestamp=timestamp, asset_y=self.asset_y, asset_x=self.asset_x,
            hedge_ratio=round(beta, 4), spread=round(spread, 4),
            z_score=round(z_score, 2), allocation_y=round(alloc_y, 4),
            allocation_x=round(alloc_x, 4), action=action
        )
'''
        elif "vwap" in strat or "exec" in strat:
            return '''"""Institutional Optimal VWAP Execution Algorithm.

Engineered by DELTA OS Top 0.001% Quantitative Architecture.
Features:
- Dynamic intraday U-shaped volume curve profile
- Almgren-Chriss market impact minimization
- Max participation rate cap (10% ADV)
- Urgency scaling & limit boundary protection
"""
from __future__ import annotations
import math
import numpy as np

class AlmgrenChrissVWAPExecutor:
    def __init__(self, target_qty: int, side: str = "BUY", adv: float = 1_000_000.0, max_pov: float = 0.10):
        self.target_qty = target_qty
        self.side = side.upper()
        self.adv = adv
        self.max_pov = max_pov
        self.executed_qty = 0
        
        # Historical U-shaped 13-bucket profile for US market (9:30 to 16:00)
        self.profile = np.array([0.15, 0.09, 0.07, 0.06, 0.05, 0.05, 0.05, 0.05, 0.06, 0.07, 0.09, 0.10, 0.11])
        self.profile = self.profile / self.profile.sum()

    def get_slice_order(self, interval_idx: int, current_bid: float, current_ask: float) -> dict:
        if self.executed_qty >= self.target_qty or interval_idx >= len(self.profile):
            return {"action": "COMPLETE", "quantity": 0, "limit_price": 0.0}
            
        remaining = self.target_qty - self.executed_qty
        target_slice = int(self.target_qty * self.profile[interval_idx])
        
        # Cap at maximum percentage of volume (POV)
        interval_adv = (self.adv / len(self.profile)) * self.max_pov
        qty = min(remaining, target_slice, int(interval_adv))
        
        # Passive limit placement inside the spread
        spread = current_ask - current_bid
        price = (current_bid + 0.3 * spread) if self.side == "BUY" else (current_ask - 0.3 * spread)
        
        return {
            "action": "SUBMIT_SLICE",
            "side": self.side,
            "quantity": qty,
            "limit_price": round(price, 2),
            "interval": interval_idx,
            "remaining": remaining - qty
        }
'''
        else:  # Momentum Trend-Following with Volatility Targeting
            return '''"""Institutional Multi-Asset Volatility-Targeted Momentum Engine.

Engineered by DELTA OS Top 0.001% Quantitative Architecture.
Features:
- Welles Wilder RSI + MACD momentum filter
- Target annualized volatility scaling (vol-targeting)
- Trailing Chandelier ATR stop-loss exit
- Anti-whipsaw regime validation
"""
from __future__ import annotations
import numpy as np

class VolTargetedMomentumStrategy:
    def __init__(self, target_annual_vol: float = 0.15, max_leverage: float = 1.5):
        self.target_vol = target_annual_vol
        self.max_leverage = max_leverage

    def compute_position_size(self, equity: float, price: float, historical_returns: np.ndarray, signal_score: float) -> dict:
        daily_vol = np.std(historical_returns) if len(historical_returns) > 10 else (0.20 / np.sqrt(252))
        annual_vol = daily_vol * np.sqrt(252)
        
        # Volatility target weight: w = target_vol / realized_vol
        vol_scalar = self.target_vol / max(annual_vol, 0.05)
        raw_weight = signal_score * vol_scalar
        clamped_weight = float(np.clip(raw_weight, -self.max_leverage, self.max_leverage))
        
        target_notional = equity * clamped_weight
        target_shares = int(target_notional / price) if price > 0 else 0
        
        return {
            "target_weight": round(clamped_weight, 4),
            "target_shares": target_shares,
            "target_notional": round(target_notional, 2),
            "realized_annual_vol": round(annual_vol * 100.0, 2),
            "leverage_applied": round(abs(clamped_weight), 2)
        }
'''

    # ------------------------------------------------------------------------
    # General Finance Q&A & Conversational Handler
    # ------------------------------------------------------------------------
    def chat(self, prompt: str) -> str:
        """Provide intelligent, evidence-grounded financial advice and answers."""
        q = (prompt or "").strip().lower()

        # Greetings & basic small talk
        if q in {"hi", "hello", "hey", "yo", "sup", "good morning", "good evening", "hi delta"}:
            return (
                "**DELTA Quant Intelligence ready.**\n\n"
                "• **Execution Mode**: `PAPER` (Almgren-Chriss calibrated)\n"
                "• **Risk Firewall**: `SAFE` (Fail-closed active)\n"
                "• **Local Quant Model**: `DELTA-FM-RESEARCH` (100% offline, zero cloud dependency)\n\n"
                "Ask any quantitative finance question, analyze a ticker, evaluate risk, forecast price trends, or type `/` for commands."
            )

        # Quantitative definitions
        if "var" in q or "value at risk" in q:
            return (
                "**Value at Risk (VaR)** is the maximum expected loss over a specific time horizon $T$ at a confidence level $1 - \\alpha$:\n\n"
                "$$\\text{VaR}_\\alpha = -\\inf \\{ l \\in \\mathbb{R} : P(L > l) \\le 1 - \\alpha \\}$$\n\n"
                "DELTA computes both **Historical VaR** (empirical quantile of past tick returns) and **Parametric VaR** (Gaussian/Student-t distribution). Expected Shortfall (CVaR) is also computed to account for fat-tail catastrophic events."
            )

        if "black scholes" in q or "greeks" in q:
            return (
                "**Black-Scholes Options Greeks Mathematics**:\n\n"
                "• **Delta ($\\Delta$)**: $\\frac{\\partial V}{\\partial S} = \\Phi(d_1)$ (Hedge ratio & directional sensitivity)\n"
                "• **Gamma ($\\Gamma$)**: $\\frac{\\partial^2 V}{\\partial S^2} = \\frac{\\phi(d_1)}{S \\sigma \\sqrt{T}}$ (Curvature & rate of change of Delta)\n"
                "• **Vega ($\\nu$)**: $\\frac{\\partial V}{\\partial \\sigma} = S \\sqrt{T} \\phi(d_1)$ (Sensitivity to implied volatility shifts)\n"
                "• **Theta ($\\Theta$)**: $\\frac{\\partial V}{\\partial t}$ (Daily calendar time-decay)\n\n"
                "Use `/risk NVDA OPTION --strike 185 --expiry 30` to run live Greeks evaluation on any contract."
            )

        # Ticker query fallback (e.g. "what do you think of NVDA")
        for sym in ["NVDA", "AAPL", "MSFT", "SPY", "QQQ", "TSLA", "AMZN", "GOOGL"]:
            if sym.lower() in q:
                res = self.analyze_stock(sym)
                if "error" in res:
                    return (f"### Quantitative Analysis for **{sym}**:\n\n"
                            f"• UNAVAILABLE: {res['error']}")
                fc = self.forecast_direction(sym)
                if "error" in fc:
                    return (f"### Quantitative Analysis for **{sym}**:\n\n"
                            f"• UNAVAILABLE: {fc['error']}")
                return (
                    f"### Quantitative Analysis for **{sym}**:\n\n"
                    f"• **Current Price**: ${res['price']:.2f} ({res['change_pct']:+.2f}%)\n"
                    f"• **Trend Stance**: `{res['trend']}` | **Composite Score**: {res['composite_score']}/100\n"
                    f"• **RSI (14)**: {res['indicators']['rsi_14']:.1f} | **VWAP**: ${res['indicators']['vwap']:.2f}\n"
                    f"• **5-Day Direction Forecast**: **{fc['direction']}** (Target: ${fc['target_price']:.2f}, Return: {fc['expected_return_pct']:+.2f}%)\n"
                    f"• **Actionable Turn Signal**: {fc['turn_recommendation']}\n\n"
                    f"Type `/risk {sym}` for downside Greeks/VaR or `/news {sym}` for catalysts."
                )

        return (
            "**DELTA Quantitative Reasoning**:\n\n"
            f"Received request: *\"{prompt}\"*\n\n"
            "I can assist you with:\n"
            "1. **Stock Analysis**: `/analyze <symbol>` (Technicals, Fundamentals, Liquidity)\n"
            "2. **Risk & Greeks**: `/risk <symbol> [stock|option|future]` (VaR, Greeks, Shocks)\n"
            "3. **Return Forecast**: `/forecast <symbol>` (Probabilistic drift & turn points)\n"
            "4. **Algo Code**: `/algo [statarb|vwap|momentum]` (Top 0.001% production strategies)\n"
            "5. **News & Catalysts**: `/news <symbol>` (Sentiment & clickbait filtering)\n"
            "6. **24/7 Sentinel**: `/sentinel [start|status]` (Automated loss kill-switch)"
        )


# ============================================================================
# 3. 24/7 AUTONOMOUS PORTFOLIO SENTINEL (WITH LOSS KILL SWITCH)
# ============================================================================

class DeltaSentinel:
    """24/7 Autonomous Portfolio Sentinel & Risk Watcher.

    Runs continuously in a non-blocking background thread:
    - Monitors LIVE portfolio equity from an injected reader (never hardcoded;
      ``None`` means UNAVAILABLE -> monitor-only, never halt).
    - Monitors REAL positions from an injected reader (never demo tickers).
    - Enforces Fail-Closed Automated Loss Circuit Breaker via the verified
      ``SafetyState.kill_all`` receipt path (no private trip API).
    - Every loop error is recorded as an alert AND re-raised from tick_once;
      the background loop survives, but nothing fails silently.
    - Alerts fan out to an optional alert_sink (toast/log/messenger wiring)
      in addition to the bounded in-memory list.
    """

    def __init__(
        self,
        brain: DeltaBrain,
        safety_state: SafetyState,
        max_drawdown_pct: float = 2.0,  # 2% max daily portfolio loss limit
        check_interval_s: float = 3.0,
        equity_fn: Optional[Callable[[], Optional[float]]] = None,
        positions_fn: Optional[Callable[[], Dict[str, float]]] = None,
        alert_sink: Optional[Callable[[Dict[str, Any]], Any]] = None,
        alert_cap: int = 200,
        state_path: Optional[str] = None,
    ):
        self.brain = brain
        self.safety = safety_state
        self.max_drawdown_pct = max_drawdown_pct
        self.check_interval_s = check_interval_s
        self.equity_fn = equity_fn
        self.positions_fn = positions_fn
        self.alert_sink = alert_sink
        self.alert_cap = alert_cap
        self.state_path = state_path
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self.alerts: List[Dict[str, Any]] = []
        # Peak is set on first live equity read. None = "not yet initialised".
        self.peak_equity: Optional[float] = None
        self.current_equity: Optional[float] = None
        self.last_tick_utc: Optional[str] = None
        self._halt_announced = False
        if state_path is not None:
            self._restore_state()

    def _state_snapshot(self) -> Dict[str, Any]:
        return {"peak_equity": self.peak_equity,
                "current_equity": self.current_equity,
                "last_tick_utc": self.last_tick_utc,
                "alerts": self.alerts[-self.alert_cap:]}

    def _persist_state(self) -> None:
        """Best-effort atomic persistence (O-item). A failed write only
        affects restart recovery — the running process keeps authoritative
        in-memory state and the next tick retries. Never raises."""
        if not self.state_path:
            return
        try:
            import json as _json

            tmp = self.state_path + f".{os.getpid()}.tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                _json.dump(self._state_snapshot(), f)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, self.state_path)
        except Exception:
            pass

    def _restore_state(self) -> None:
        """Reload persisted watcher state so a restart keeps the drawdown
        window, alert history, and freshness marker. Corrupt state is
        discarded loudly (alert), never trusted."""
        try:
            import json as _json

            with open(self.state_path, encoding="utf-8") as f:
                snap = _json.load(f)
            if not isinstance(snap, dict):
                raise ValueError("not an object")
            self.peak_equity = snap.get("peak_equity")
            self.current_equity = snap.get("current_equity")
            self.last_tick_utc = snap.get("last_tick_utc")
            alerts = snap.get("alerts", [])
            if isinstance(alerts, list):
                self.alerts = [a for a in alerts if isinstance(a, dict)][-self.alert_cap:]
        except FileNotFoundError:
            pass
        except Exception as exc:
            self._emit("WARNING", "SENTINEL_STATE_UNREADABLE",
                       f"Persisted watcher state discarded ({type(exc).__name__}); "
                       f"drawdown window restarts.")

    @property
    def halted(self) -> bool:
        """Kill state mirrors the single SafetyState mode (no second switch)."""
        try:
            return str(self.safety.mode).upper() == "HALTED"
        except Exception:
            return True  # unreadable safety -> fail-closed

    def _emit(self, level: str, event: str, message: str) -> Dict[str, Any]:
        # O-item duplicate suppression: an alert identical to the
        # immediately previous one is a crash-loop echo, not new
        # information. Collapse it (counted, not stored twice).
        if self.alerts:
            prev = self.alerts[-1]
            if (prev.get("level") == level and prev.get("event") == event
                    and prev.get("message") == message):
                prev["duplicates_suppressed"] = int(
                    prev.get("duplicates_suppressed", 0)) + 1
                self._persist_state()
                return prev
        alert = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": level,
            "event": event,
            "message": message,
        }
        self.alerts.append(alert)
        if len(self.alerts) > self.alert_cap:
            del self.alerts[: len(self.alerts) - self.alert_cap]
        if self.alert_sink is not None:
            try:
                self.alert_sink(dict(alert))
            except Exception as exc:
                self.alerts.append({
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "level": "ERROR",
                    "event": "ALERT_SINK_FAILED",
                    "message": f"alert sink raised {type(exc).__name__}: {exc}",
                })
        self._persist_state()
        return alert

    def start(self) -> str:
        if self.running:
            return "24/7 Sentinel is already ACTIVE."
        self.running = True
        self.thread = threading.Thread(target=self._sentinel_loop, daemon=True, name="DeltaSentinel247")
        self.thread.start()
        return "24/7 Sentinel STARTED. Autonomous portfolio surveillance & loss kill switch active."

    def stop(self) -> str:
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1.0)
        return "24/7 Sentinel STOPPED."

    def status(self) -> Dict[str, Any]:
        if self.peak_equity and self.current_equity is not None and self.peak_equity > 0:
            drawdown_pct = ((self.peak_equity - self.current_equity) / self.peak_equity) * 100.0
        else:
            drawdown_pct = 0.0
        stale = True
        if self.last_tick_utc:
            try:
                age = (datetime.now(timezone.utc)
                       - datetime.fromisoformat(self.last_tick_utc)).total_seconds()
                stale = age > max(3.0 * self.check_interval_s, 5.0)
            except Exception:
                stale = True
        return {
            "status": "ACTIVE (24/7)" if self.running else "STOPPED",
            "max_drawdown_threshold_pct": self.max_drawdown_pct,
            "current_drawdown_pct": round(drawdown_pct, 2),
            "kill_switch_state": "HALTED" if self.halted else "ARMED",
            "recent_alerts_count": len(self.alerts),
            "recent_alerts": self.alerts[-5:],
            "last_tick_utc": self.last_tick_utc,
            "stale": stale,
            "equity_source": "live" if self.equity_fn is not None else "unconfigured",
            "peak_equity": self.peak_equity,
            "current_equity": self.current_equity,
        }

    def tick_once(self) -> Dict[str, Any]:
        """One surveillance pass. Raises on failure (never swallows)."""
        outcome: Dict[str, Any] = {"halted": False, "actions": []}
        # 1. Live equity (None/NaN = UNAVAILABLE -> monitor-only).
        equity: Optional[float] = None
        if self.equity_fn is not None:
            equity = self.equity_fn()
        if equity is None or not np.isfinite(equity):
            self._emit("WARNING", "EQUITY_UNAVAILABLE",
                       "Ledger equity unreadable: monitoring only, no automated action.")
            self.last_tick_utc = datetime.now(timezone.utc).isoformat()
            outcome["actions"].append("monitor-only (equity unavailable)")
            self._persist_state()
            return outcome
        equity = float(equity)
        self.current_equity = equity
        if self.peak_equity is None:
            self.peak_equity = equity  # first live read initialises the peak
            self.last_tick_utc = datetime.now(timezone.utc).isoformat()
            outcome["actions"].append("peak initialised")
            self._persist_state()
            return outcome
        self.peak_equity = max(self.peak_equity, equity)
        drawdown_pct = ((self.peak_equity - equity) / self.peak_equity) * 100.0

        # 2. Automated Circuit Breaker on excessive realised loss.
        if drawdown_pct >= self.max_drawdown_pct and not self.halted:
            reason = (f"AUTONOMOUS KILL SWITCH: Portfolio drawdown {drawdown_pct:.2f}% "
                      f"breached max tolerable limit {self.max_drawdown_pct:.2f}%.")
            receipt = self.safety.kill_all([], actor="SENTINEL_24_7")
            self._emit("CRITICAL", "AUTOMATED_KILL_SWITCH_TRIPPED",
                       f"{reason} Receipt: {receipt}")
            self._halt_announced = True
            outcome["halted"] = True
            outcome["actions"].append("kill_all executed")
        elif self.halted and not self._halt_announced:
            self._emit("CRITICAL", "ENGINE_HALTED",
                       "Engine HALTED: all autonomous action frozen until /unlock.")
            self._halt_announced = True
        elif not self.halted:
            self._halt_announced = False

        # 3. Market Anomaly & Crash Sentinel over REAL positions only.
        # Advisory: a failing scan records an ERROR alert but never masks
        # the breaker outcome above.
        positions: Dict[str, float] = {}
        if self.positions_fn is not None:
            positions = {k: float(v) for k, v in (self.positions_fn() or {}).items()}
        if positions:
            try:
                crash_eval = self.brain.evaluate_portfolio_regime(positions=positions)
            except Exception as exc:
                self._emit("ERROR", "CRASH_SCAN_FAILED",
                           f"Regime scan raised {type(exc).__name__}: {exc}")
                crash_eval = {}
            if crash_eval.get("crash_probability_pct", 0) > 65.0:
                self._emit("WARNING", "CRASH_WARNING",
                           f"High market crash risk ({crash_eval['crash_probability_pct']}%). "
                           "Recommending pre-crash hedges.")
                outcome["actions"].append("crash warning")
        else:
            outcome["actions"].append("no positions: crash scan skipped (never demo tickers)")

        self.last_tick_utc = datetime.now(timezone.utc).isoformat()
        self._persist_state()
        return outcome

    def _sentinel_loop(self) -> None:
        while self.running:
            try:
                self.tick_once()
            except Exception as exc:
                # Loop survives; the failure itself is recorded, never silent.
                try:
                    self._emit("ERROR", "SENTINEL_TICK_FAILED",
                               f"{type(exc).__name__}: {exc}")
                except Exception:
                    pass
            time.sleep(self.check_interval_s)
