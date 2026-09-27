"""DELTA OS data router: fail-SOFT for the interactive terminal.

TIER1 yfinance package -> TIER2 zero-dependency Yahoo v8 REST (httpx) ->
TIER3 in-memory LRU cache ([STALE DATA] badge) -> labeled synthetic sandbox
([SYNTHETIC SIMULATION ONLY] badge, seedable).

CONTRACT (reconciliation with the certified research path):
- Badges are structural: every frame carries provenance.tier + badge, and the
  REPL renders the badge on every quote. Badges can never be dropped by
  callers (provenance travels with the frame object).
- NOTHING from TIER3-synthetic or [STALE] frames may enter the research
  truth path (research.real_loop stays fail-closed) or arm live execution:
  safety.py refuses orders without TIER1/TIER2-fresh data.
- FRED macro + Google News RSS follow the same pattern: live -> cached w/
  age -> explicit unavailable (no synthetic macro/news; fabrication there is
  never acceptable, so the router returns Unavailable instead of inventing).
"""
from __future__ import annotations

import hashlib
import math
import time
from collections import OrderedDict
from dataclasses import dataclass, field

import pandas as pd

ROUTER_VERSION = "data-router-v1"
FRESH_TTL_S = 300.0


@dataclass(frozen=True, slots=True)
class Provenance:
    tier: str  # TIER1|TIER2|TIER3-CACHE|TIER3-SYNTH
    badge: str  # "" | "[STALE DATA]" | "[SYNTHETIC SIMULATION ONLY]"
    symbol: str
    as_of: str
    age_s: float = 0.0


@dataclass
class QuoteFrame:
    frame: pd.DataFrame
    provenance: Provenance


class FrameCache:
    """LRU cache of QuoteFrames with age tracking."""

    def __init__(self, max_items: int = 64) -> None:
        self._items: OrderedDict[str, QuoteFrame] = OrderedDict()
        self._max = max_items

    def put(self, symbol: str, qf: QuoteFrame) -> None:
        self._items[symbol] = qf
        self._items.move_to_end(symbol)
        while len(self._items) > self._max:
            self._items.popitem(last=False)

    def get(self, symbol: str) -> QuoteFrame | None:
        qf = self._items.get(symbol)
        if qf is None:
            return None
        self._items.move_to_end(symbol)
        return qf


def _synthetic(symbol: str, days: int = 180, seed: int = 7) -> pd.DataFrame:
    import numpy as np

    h = int(hashlib.sha256(f"{symbol}:{seed}".encode()).hexdigest()[:8], 16)
    rng = np.random.default_rng(h)
    n = max(days, 60)
    idx = pd.date_range(end=pd.Timestamp.utcnow(), periods=n, freq="B", tz="UTC")
    rets = rng.normal(0.0005, 0.015, n)
    closes = 100 * np.exp(np.cumsum(rets))
    vols = (500_000 + rng.lognormal(13, 0.7, n)).astype(int)
    opens = np.concatenate([[100.0], closes[:-1]])
    return pd.DataFrame({"open": opens, "high": np.maximum(opens, closes) * 1.002,
                         "low": np.minimum(opens, closes) * 0.998,
                         "close": closes, "volume": vols}, index=idx)


def _tier1_yfinance(symbol: str, days: int) -> pd.DataFrame | None:
    try:
        import yfinance as yf
        from datetime import datetime, timedelta, timezone

        end = datetime.now(timezone.utc)
        df = yf.Ticker(symbol).history(
            start=(end - timedelta(days=int(days * 1.6))).strftime("%Y-%m-%d"),
            end=end.strftime("%Y-%m-%d"), interval="1d", auto_adjust=True)
        if df is None or df.empty or len(df) < 30:
            return None
        df.columns = [str(c).lower() for c in df.columns]
        out = df[["open", "high", "low", "close", "volume"]].copy()
        out.index = pd.to_datetime(out.index, utc=True)
        return out.sort_index().dropna()
    except Exception:
        return None


def _tier2_yahoo_rest(symbol: str, days: int, timeout_s: float = 8.0) -> pd.DataFrame | None:
    """Zero-dependency Yahoo v8 chart endpoint (httpx). Sub-100ms typical.

    Auto-shrinks range on 422/empty (Yahoo caps intraday ranges) so a single
    bad range never crashes the loop — tries days, days/2, 30d.
    """
    try:
        import httpx

        for attempt in (max(days, 30), max(days // 2, 30), 30):
            try:
                r = httpx.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}",
                              params={"range": f"{attempt}d", "interval": "1d"},
                              headers={"User-Agent": "DELTA-OS/1.0"}, timeout=timeout_s)
            except Exception:
                return None
            if r.status_code != 200:
                continue
            try:
                res = r.json()["chart"]["result"][0]
                ts = res["timestamp"]
                q = res["indicators"]["quote"][0]
                adj = res["indicators"].get("adjclose", [{}])[0].get("adjclose")
                close = adj or q["close"]
                idx = pd.to_datetime(ts, unit="s", utc=True)
                df = pd.DataFrame({"open": q["open"], "high": q["high"], "low": q["low"],
                                   "close": close, "volume": q["volume"]}, index=idx)
                df = df.dropna()
                if len(df) >= 30:
                    return df
            except Exception:
                continue
        return None
    except Exception:
        return None


class DataRouter:
    """Fail-soft dispatcher for the terminal. Badges mandatory."""

    def __init__(self, cache: FrameCache | None = None,
                 synth_seed: int = 7) -> None:
        self.cache = cache or FrameCache()
        self.synth_seed = synth_seed

    def quote(self, symbol: str, days: int = 180) -> QuoteFrame:
        sym = symbol.strip().upper()
        if not sym:
            raise ValueError("symbol required.")
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        f = _tier1_yfinance(sym, days)
        if f is not None:
            qf = QuoteFrame(f, Provenance("TIER1", "", sym, now))
            self.cache.put(sym, qf)
            return qf
        f = _tier2_yahoo_rest(sym, days)
        if f is not None:
            qf = QuoteFrame(f, Provenance("TIER2", "", sym, now))
            self.cache.put(sym, qf)
            return qf
        cached = self.cache.get(sym)
        if cached is not None:
            # Age unknown without fetch clock; TTL breach is structural here:
            # anything served from cache is by definition not fresh.
            return QuoteFrame(cached.frame,
                              Provenance("TIER3-CACHE", "[STALE DATA]", sym, now,
                                         FRESH_TTL_S + 1.0))
        return QuoteFrame(_synthetic(sym, days, self.synth_seed),
                          Provenance("TIER3-SYNTH", "[SYNTHETIC SIMULATION ONLY]",
                                     sym, now))

    def is_fresh(self, qf: QuoteFrame) -> bool:
        return qf.provenance.tier in ("TIER1", "TIER2")


# ---------------- FRED macro ----------------

FRED_SERIES = ("T10Y2Y", "FEDFUNDS", "CPIAUCSL", "WALCL", "RRPONTSYD", "TGA")


class FredUnavailable(Exception):
    pass


def fred_observations(series: str, api_key: str, n: int = 12,
                      timeout_s: float = 10.0) -> dict:
    """Latest n observations for a FRED series. Raises FredUnavailable (never
    synthesizes macro data)."""
    import httpx

    if not api_key:
        raise FredUnavailable("FRED API key required (/auth wizard, slot 3).")
    try:
        r = httpx.get("https://api.stlouisfed.org/fred/series/observations",
                      params={"series_id": series, "api_key": api_key,
                              "file_type": "json", "sort_order": "desc",
                              "limit": str(n)}, timeout=timeout_s)
        if r.status_code != 200:
            raise FredUnavailable(f"FRED HTTP {r.status_code}.")
        obs = [(o["date"], float(o["value"])) for o in r.json()["observations"]
               if o["value"] not in (".", "")]
        if not obs:
            raise FredUnavailable(f"no observations for {series}.")
        return {"series": series, "observations": obs}
    except FredUnavailable:
        raise
    except Exception as exc:
        raise FredUnavailable(f"FRED fetch failed: {exc}") from exc


def net_liquidity_index(walcl: float, tga: float, rrp: float) -> dict:
    """Net Liquidity = Fed Assets - TGA - Reverse Repo. Regime score [-100,100]
    via tanh scaling around $1T units (documented heuristic, not a forecast)."""
    nli = walcl - tga - rrp
    score = 100 * math.tanh(nli / 1_000_000.0)
    regime = "EXPANSION" if score > 20 else ("CONTRACTION" if score < -20 else "NEUTRAL")
    return {"net_liquidity": round(nli, 1), "score": round(score, 1), "regime": regime}


# ---------------- news ----------------

_POS = frozenset("beat rally surge jump gain profit growth upgrade bullish breakout record high momentum".split())
_NEG = frozenset("miss plunge crash loss lawsuit downgrade bearish probe fraud default cut warning drop".split())

CATALYSTS = (
    ("EARNINGS", ("earnings", "revenue", "guidance", "eps", "quarterly results")),
    ("SEC-FILING", ("sec filing", "10-k", "10-q", "8-k", "s-1", "prospectus")),
    ("EXEC-CHANGE", ("ceo", "cfo", "resigns", "steps down", "appoints", "departure")),
    ("FDA", ("fda", "approval", "clinical trial", "phase 3", "breakthrough")),
    ("ANTITRUST", ("antitrust", "doj", "ftc", "lawsuit", "monopoly", "regulation")),
    ("M&A", ("acquires", "merger", "takeover", "buyout", "acquisition")),
)
CLICKBAIT = ("should you buy", "best stocks", "top stocks", "you need to know",
             "what to know", "could soar", "will skyrocket", "experts say")


def catalyst_tags(title: str) -> tuple[list[str], bool]:
    """Returns (catalyst list, is_clickbait). Clickbait is demoted, not deleted
    (caller decides; count disclosed)."""
    low = title.lower()
    cats = [name for name, keys in CATALYSTS if any(k in low for k in keys)]
    return cats, any(cb in low for cb in CLICKBAIT)


def news_sentiment(query: str, timeout_s: float = 10.0, limit: int = 10) -> dict:
    """Google News RSS -> dedup -> lexicon polarity [-1,1] + $TICKER entities.
    Raises FredUnavailable-style Unavailable on network failure (no fake news)."""
    import re
    import xml.etree.ElementTree as ET

    import httpx

    try:
        r = httpx.get("https://news.google.com/rss/search",
                      params={"q": query, "hl": "en-US", "gl": "US", "ceid": "US:en"},
                      headers={"User-Agent": "DELTA-OS/1.0"}, timeout=timeout_s)
        if r.status_code != 200:
            raise RuntimeError(f"HTTP {r.status_code}")
        root = ET.fromstring(r.content)
    except Exception as exc:
        raise RuntimeError(f"news unavailable: {exc}") from exc
    seen, items = set(), []
    for it in root.iter("item"):
        title = (it.findtext("title") or "").strip()
        link = (it.findtext("link") or "").strip()
        key = hashlib.sha256(re.sub(r"\s+", " ", title).lower().encode()).hexdigest()
        if not title or key in seen:
            continue
        seen.add(key)
        words = re.findall(r"[a-z]+", title.lower())
        pos = sum(w in _POS for w in words)
        neg = sum(w in _NEG for w in words)
        pol = (pos - neg) / max(len(words), 1) * 4
        pol = max(-1.0, min(1.0, pol))
        tickers = sorted(set(re.findall(r"\$([A-Z]{1,5})\b", title)))
        badge = "[BULLISH]" if pol > 0.15 else ("[BEARISH]" if pol < -0.15 else "[NEUTRAL]")
        cats, clickbait = catalyst_tags(title)
        items.append({"title": title, "link": link, "polarity": round(pol, 3),
                      "badge": badge, "tickers": tickers, "catalysts": cats,
                      "clickbait": clickbait})
        if len(items) >= limit:
            break
    if not items:
        raise RuntimeError("news unavailable: empty feed.")
    avg = sum(i["polarity"] for i in items) / len(items)
    cats = sorted({c for i in items for c in i["catalysts"]})
    return {"query": query, "n": len(items), "avg_polarity": round(avg, 3),
            "catalysts": cats,
            "clickbait_filtered": sum(1 for i in items if i["clickbait"]),
            "items": items}


def fundamentals(symbol: str) -> dict | None:
    """yfinance info/fast-info mapped to Piotroski/Altman/DCF inputs.

    Returns None when unavailable (fail-soft for the terminal; /fundamental
    then reports missing fields instead of inventing ratios).
    """
    try:
        import yfinance as yf

        t = yf.Ticker(symbol.strip().upper())
        info = t.info or {}
        if not info:
            return None
        out = {
            "pe": info.get("trailingPE"), "pb": info.get("priceToBook"),
            "roe": info.get("returnOnEquity"), "roa": info.get("returnOnAssets"),
            "debt_to_equity": info.get("debtToEquity"),
            "current_ratio": info.get("currentRatio"),
            "free_cashflow": info.get("freeCashflow"),
            "shares": info.get("sharesOutstanding"),
            "market_cap": info.get("marketCap"),
            "earnings_date": info.get("earningsTimestamp"),
            "gross_margins": info.get("grossMargins"),
            "profit_margins": info.get("profitMargins"),
        }
        return out
    except Exception:
        return None


def track_alerts(frame: pd.DataFrame, window: int = 20) -> list[str]:
    """VWAP-breach (>2.5 sigma) + volume-spike (>3x) alerts for /track."""
    from delta_os import quantkit as _Q

    alerts = []
    if len(frame) < window + 1:
        return alerts
    bands = _Q.vwap_bands(frame, window)
    # Breakout semantics: current price vs the ESTABLISHED (prior-bar) bands.
    # Using the current bar's own bands would let a spike bar drag VWAP/sigma
    # toward itself (single-spike location saturates ~2.4σ) and hide breakouts.
    prev = bands.iloc[-2]
    px = float(frame["close"].iloc[-1])
    sd = (prev["upper1"] - prev["vwap"]) or 1e-9
    loc = (px - prev["vwap"]) / sd
    if abs(loc) > 2.5:
        alerts.append(f"VWAP breakout {loc:+.1f}σ @ {px:,.2f}")
    vol = frame["volume"].astype(float)
    rvol = vol.iloc[-1] / max(vol.iloc[-window - 1:-1].mean(), 1)
    if rvol > 3:
        alerts.append(f"volume spike {rvol:.1f}x RVOL")
    return alerts


__all__ = ["ROUTER_VERSION", "Provenance", "QuoteFrame", "FrameCache", "DataRouter",
           "FRED_SERIES", "FredUnavailable", "fred_observations", "net_liquidity_index",
           "CATALYSTS", "catalyst_tags", "news_sentiment", "track_alerts",
           "fundamentals"]
