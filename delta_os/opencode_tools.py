"""OpenCode bridge: the 5 domains as callable Python tools.

Domains:
  1. financial-data  -> delta_os.data_router.DataRouter.quote (+ badges)
  2. india-market    -> delta_os.india_market.quote / universe / market_status
  3. indicators      -> quant.indicators.summarize / render_card
  4. reasonforge-logic -> decision.reasonforge.analyze (synthesis)
  5. statistics      -> delta_os.statistics_hub.describe / render_card

Each function returns JSON-serializable dicts (frames excluded; use
`include_frame=False` default). Used by:
- delta_os.llm_gateway.research_tools (ReAct TOOL: lines)
- tools/delta_mcp.py (local MCP server for external `opencode` CLI)
- delta_os.repl slash commands (/india /indicators /stats /reason /quote)
"""
from __future__ import annotations

BRIDGE_VERSION = "opencode-bridge-v1"


def tool_financial_data(symbol: str, days: int = 180) -> dict:
    """Live quote w/ provenance badge (US + global; India-aware passthrough)."""
    from delta_os.data_router import DataRouter

    sym = (symbol or "").strip().upper()
    if not sym:
        raise ValueError("symbol required.")
    # Route Indian stems through the India gateway so RELIANCE -> RELIANCE.NS.
    try:
        from delta_os import india_market as IN
        ysym = IN.normalize_auto(sym)
    except Exception:
        ysym = sym
    qf = DataRouter().quote(ysym, days=int(days))
    f = qf.frame
    last = float(f["close"].iloc[-1])
    chg = float(last / float(f["close"].iloc[-2]) - 1) if len(f) > 1 else 0.0
    return {"domain": "financial-data", "symbol": sym, "yahoo_symbol": ysym,
            "price": round(last, 2), "change_pct": round(chg * 100, 2),
            "bars": len(f), "tier": qf.provenance.tier,
            "badge": qf.provenance.badge}


def tool_india_market(symbol: str, days: int = 180,
                      exchange: str = "AUTO") -> dict:
    """NSE/BSE quote + IST session state."""
    from delta_os import india_market as IN

    q = IN.quote(symbol, days=int(days), exchange=exchange)
    out = {k: v for k, v in q.items() if k != "frame"}
    out["domain"] = "india-market"
    out["bars"] = len(q["frame"])
    return out


def tool_india_universe(sector: str | None = None,
                        exchange: str = "NSE") -> dict:
    from delta_os import india_market as IN
    syms = IN.universe(sector=sector, exchange=exchange)
    return {"domain": "india-market", "exchange": exchange.upper(),
            "sector": (sector or "NIFTY50").upper(),
            "count": len(syms), "symbols": syms,
            "market": IN.market_status()}


def tool_indicators(symbol: str, days: int = 252,
                    exchange: str = "AUTO") -> dict:
    """Full indicator card (RSI/MACD/Bollinger/Stoch/ATR/ADX/VWAP)."""
    from delta_os import india_market as IN
    from delta_os import indicators as TD

    q = IN.quote(symbol, days=int(days), exchange=exchange)
    summary = TD.summarize(q["frame"])
    card = TD.render_card(symbol, summary)
    return {"domain": "indicators", "symbol": symbol.strip().upper(),
            "yahoo_symbol": q["yahoo_symbol"], "tier": q["tier"],
            "badge": q["badge"], "summary": summary, "card": card}


def tool_statistics(symbol: str, days: int = 252,
                    exchange: str = "AUTO") -> dict:
    """Stats card (cumret/vol/Sharpe/Sortino/MaxDD/VaR/CVaR/beta)."""
    from delta_os import india_market as IN
    from delta_os import statistics_hub as SH

    q = IN.quote(symbol, days=int(days), exchange=exchange)
    mkt = None
    try:  # beta vs NIFTY for Indian legs, SPY otherwise
        bench = "^NSEI" if q["yahoo_symbol"].endswith((".NS", ".BO")) or q["yahoo_symbol"].startswith("^") else "SPY"
        from delta_os.data_router import DataRouter
        mkt = DataRouter().quote(bench, days=int(days)).frame["close"]
    except Exception:
        mkt = None
    stats = SH.describe(q["frame"], market=mkt)
    card = SH.render_card(symbol, stats)
    return {"domain": "statistics", "symbol": symbol.strip().upper(),
            "yahoo_symbol": q["yahoo_symbol"], "tier": q["tier"],
            "badge": q["badge"], "statistics": stats, "card": card}


def tool_reasonforge(symbol: str, days: int = 252,
                     exchange: str = "AUTO") -> dict:
    """ReasonForge synthesis: score + stance + reasons/risks + tradable."""
    from delta_os import reasonforge as RF

    v = RF.analyze(symbol, days=int(days), exchange=exchange)
    return {"domain": "reasonforge-logic", "symbol": v.symbol,
            "yahoo_symbol": v.yahoo_symbol, "price": v.price,
            "stance": v.stance, "confidence": v.confidence,
            "score": v.score, "reasons": v.reasons, "risks": v.risks,
            "tier": v.tier, "badge": v.badge, "tradable": v.tradable,
            "indicators": v.indicators, "statistics": v.statistics,
            "card": v.render()}


TOOLS = {
    "financial_data": tool_financial_data,
    "india_market": tool_india_market,
    "india_universe": tool_india_universe,
    "indicators": tool_indicators,
    "statistics": tool_statistics,
    "reasonforge": tool_reasonforge,
}

__all__ = ["BRIDGE_VERSION", "TOOLS", "tool_financial_data",
           "tool_india_market", "tool_india_universe", "tool_indicators",
           "tool_statistics", "tool_reasonforge"]
