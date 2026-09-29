"""DELTA OS India market gateway: NSE/BSE via Yahoo Finance suffixes.

Canonical module for the `india-market` domain requested for OpenCode wiring.

- Symbol normalization: RELIANCE -> RELIANCE.NS, RELIANCE.BO explicit OK,
  US symbols pass through untouched. NIFTY/BANKNIFTY indices mapped to
  ^NSEI / ^NSEBANK.
- Market hours: NSE 09:15-15:30 IST Mon-Fri (IST = UTC+5:30).
- Quotes reuse delta_os.data_router.DataRouter so provenance badges
  (TIER1/TIER2/STALE/SYNTH) and fail-soft guarantees are preserved.
- NIFTY50 universe + sectors for screening / ReasonForge context.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any

INDIA_MARKET_VERSION = "india-market-v1"

NSE_SUFFIX = ".NS"
BSE_SUFFIX = ".BO"

INDEX_MAP = {
    "NIFTY": "^NSEI",
    "NIFTY50": "^NSEI",
    "NIFTY_50": "^NSEI",
    "BANKNIFTY": "^NSEBANK",
    "BANK_NIFTY": "^NSEBANK",
    "SENSEX": "^BSESN",
    "INDIA_VIX": "^INDIAVIX",
}

# NIFTY50 constituents (symbol stems, NSE). Refreshed Sep-2026 review.
NIFTY50 = [
    "RELIANCE", "HDFCBANK", "ICICIBANK", "INFY", "TCS", "BHARTIARTL",
    "SBIN", "ITC", "KOTAKBANK", "LT", "HINDUNILVR", "AXISBANK",
    "ASIANPAINT", "MARUTI", "TITAN", "SUNPHARMA", "TATAMOTORS",
    "TATASTEEL", "NTPC", "ONGC", "POWERGRID", "ULTRACEMCO",
    "NESTLEIND", "JSWSTEEL", "HCLTECH", "WIPRO", "COALINDIA",
    "TECHM", "BAJFINANCE", "BAJAJFINSV", "HDFCLIFE", "SBILIFE",
    "ADANIENT", "ADANIPORTS", "APOLLOHOSP", "BRITANNIA",
    "CIPLA", "DIVISLAB", "DRREDDY", "EICHERMOT", "GRASIM",
    "HEROMOTOCO", "HINDALCO", "INDUSINDBK", "M&M", "SHRIRAMFIN",
    "TATACONSUM", "TRENT", "BPCL", "BAJAJ-AUTO",
]

SECTORS = {
    "BANKING": ["HDFCBANK", "ICICIBANK", "SBIN", "KOTAKBANK", "AXISBANK", "INDUSINDBK"],
    "IT": ["INFY", "TCS", "HCLTECH", "WIPRO", "TECHM"],
    "ENERGY": ["RELIANCE", "ONGC", "NTPC", "POWERGRID", "COALINDIA", "BPCL"],
    "AUTO": ["MARUTI", "TATAMOTORS", "EICHERMOT", "HEROMOTOCO", "M&M"],
    "PHARMA": ["SUNPHARMA", "CIPLA", "DIVISLAB", "DRREDDY", "APOLLOHOSP"],
    "FMCG": ["ITC", "HINDUNILVR", "NESTLEIND", "BRITANNIA", "TATACONSUM"],
}

IST = timezone(timedelta(hours=5, minutes=30))


def normalize_symbol(symbol: str, exchange: str = "NSE") -> str:
    """Normalize user input to a Yahoo-fetchable symbol.

    - 'RELIANCE' + NSE -> 'RELIANCE.NS'
    - 'RELIANCE.BO' stays explicit (BSE wins over exchange arg)
    - '^NSEI', US 'AAPL', 'RELIANCE.NS' pass through
    - 'NIFTY' -> '^NSEI', 'SENSEX' -> '^BSESN'
    """
    s = (symbol or "").strip().upper().replace(" ", "")
    if not s:
        raise ValueError("symbol required.")
    if s in INDEX_MAP:
        return INDEX_MAP[s]
    if s.startswith("^") or "." in s or "-" in s:
        # Already qualified (^NSEI, RELIANCE.NS, US HYPHEN) or US plain
        if "." in s or s.startswith("^"):
            return s
        return s  # US equity passthrough
    # Bare Indian stem?
    if s in NIFTY50 or exchange.upper() in ("NSE", "BSE", "NS", "BO"):
        suffix = BSE_SUFFIX if exchange.upper() in ("BSE", "BO") else NSE_SUFFIX
        # Heuristic: if it looks like a known NIFTY stem OR caller asked
        # for an Indian exchange, qualify. US single names (AAPL/MSFT/NVDA)
        # are only qualified when exchange is explicitly Indian.
        if s in NIFTY50 or s in {x for v in SECTORS.values() for x in v}:
            return f"{s}{suffix}"
        if exchange.upper() in ("NSE", "BSE", "NS", "BO"):
            # Only qualify when the caller context is India; the quote()
            # wrapper below defaults exchange="AUTO" to avoid hijacking US.
            return f"{s}{suffix}"
    return s


def normalize_auto(symbol: str) -> str:
    """AUTO mode: qualify only known Indian stems/indices, else passthrough."""
    s = (symbol or "").strip().upper().replace(" ", "")
    if not s:
        raise ValueError("symbol required.")
    if s in INDEX_MAP:
        return INDEX_MAP[s]
    if s.startswith("^") or "." in s:
        return s
    if s in NIFTY50 or s in {x for v in SECTORS.values() for x in v}:
        return f"{s}{NSE_SUFFIX}"
    return s


def market_status(now_utc: datetime | None = None) -> dict:
    """NSE session state. Returns {market, exchange, ist_time, reason}."""
    now_utc = now_utc or datetime.now(timezone.utc)
    ist = now_utc.astimezone(IST)
    weekday = ist.weekday()  # 0=Mon
    mins = ist.hour * 60 + ist.minute
    open_m, close_m = 9 * 60 + 15, 15 * 60 + 30
    if weekday >= 5:
        return {"market": "CLOSED", "exchange": "NSE",
                "ist_time": ist.strftime("%Y-%m-%d %H:%M IST"),
                "reason": "weekend"}
    if open_m <= mins < close_m:
        return {"market": "OPEN", "exchange": "NSE",
                "ist_time": ist.strftime("%Y-%m-%d %H:%M IST"),
                "reason": "regular session"}
    if mins < open_m:
        return {"market": "PRE-OPEN", "exchange": "NSE",
                "ist_time": ist.strftime("%Y-%m-%d %H:%M IST"),
                "reason": "before 09:15 IST"}
    return {"market": "CLOSED", "exchange": "NSE",
            "ist_time": ist.strftime("%Y-%m-%d %H:%M IST"),
            "reason": "after 15:30 IST"}


def quote(symbol: str, days: int = 180, exchange: str = "AUTO") -> dict:
    """Fetch OHLCV via DataRouter with badge + INR context.

    Returns {"symbol", "yahoo_symbol", "price", "change_pct", "tier",
    "badge", "market", "frame"} — frame kept for indicators/statistics.
    """
    from delta_os.data_router import DataRouter

    ysym = normalize_auto(symbol) if exchange.upper() == "AUTO" else normalize_symbol(symbol, exchange)
    router = DataRouter()
    qf = router.quote(ysym, days=days)
    f = qf.frame
    last = float(f["close"].iloc[-1])
    chg = float(last / float(f["close"].iloc[-2]) - 1) if len(f) > 1 else 0.0
    return {
        "symbol": symbol.strip().upper(),
        "yahoo_symbol": ysym,
        "price": round(last, 2),
        "change_pct": round(chg * 100, 2),
        "tier": qf.provenance.tier,
        "badge": qf.provenance.badge,
        "market": market_status(),
        "currency": "INR" if ysym.endswith((".NS", ".BO")) or ysym.startswith("^") else "USD",
        "frame": f,
    }


def universe(sector: str | None = None, exchange: str = "NSE") -> list[str]:
    """NIFTY50 stems qualified for `exchange` (default NSE -> .NS)."""
    suffix = BSE_SUFFIX if exchange.upper() in ("BSE", "BO") else NSE_SUFFIX
    if sector:
        stems = SECTORS.get(sector.strip().upper(), [])
    else:
        stems = NIFTY50
    return [f"{s}{suffix}" for s in stems]


__all__ = ["INDIA_MARKET_VERSION", "NIFTY50", "SECTORS", "INDEX_MAP",
           "normalize_symbol", "normalize_auto", "market_status",
           "quote", "universe"]
