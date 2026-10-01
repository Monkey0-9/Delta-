"""PIT-safe fundamentals provider — replaces feature_engine placeholder.

Design: cache-first, fail-closed.
- Primary: SEC EDGAR XBRL cache (`sec-edgar` tools / local cache dir).
- Optional: yfinance snapshot (explicitly labeled, never silently mixed).
- Every value carries (filing_date, period_end, source) so features can enforce
  PIT: value usable at ts iff filing_date <= ts.

Until a live backfill runs, `get()` raises FundamentalsUnavailable — and
`ValueFeature` propagates instead of returning NaN. That is the honest
behavior required by STUB_AUDIT #3.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


class FundamentalsUnavailable(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class FundamentalPoint:
    symbol: str
    metric: str  # e.g. pe, pb, roe, eps_ttm, debt_equity
    value: float
    period_end: str  # YYYY-MM-DD
    filing_date: str  # YYYY-MM-DD (PIT cutoff)
    source: str  # edgar|yfinance_snapshot|cache


class FundamentalsProvider:
    """Cache-first PIT provider. cache_dir holds <SYM>_<metric>.json rows."""

    def __init__(self, cache_dir: str | Path = "data/fundamentals_cache",
                 allow_snapshot: bool = False) -> None:
        self.cache_dir = Path(cache_dir)
        self.allow_snapshot = allow_snapshot

    def _read_cache(self, symbol: str, metric: str) -> list[FundamentalPoint]:
        import json
        p = self.cache_dir / f"{symbol.upper()}_{metric.lower()}.json"
        if not p.exists():
            return []
        try:
            rows = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return []
        out: list[FundamentalPoint] = []
        for r in rows if isinstance(rows, list) else []:
            try:
                out.append(FundamentalPoint(symbol.upper(), metric.lower(), float(r["value"]),
                                           str(r["period_end"]), str(r["filing_date"]),
                                           str(r.get("source", "cache"))))
            except Exception:
                continue
        return sorted(out, key=lambda x: x.filing_date)

    def get(self, symbol: str, metric: str, as_of: str | datetime) -> FundamentalPoint:
        """Latest point with filing_date <= as_of. Raises when none."""
        asof = as_of if isinstance(as_of, str) else as_of.date().isoformat()
        pts = [p for p in self._read_cache(symbol, metric) if p.filing_date <= asof]
        if pts:
            return pts[-1]
        if self.allow_snapshot:
            snap = self._snapshot(symbol, metric)
            if snap is not None and snap.filing_date <= asof:
                return snap
        raise FundamentalsUnavailable(
            f"no PIT fundamentals for {symbol.upper()}/{metric.lower()} as_of={asof} "
            f"(backfill data/fundamentals_cache or wire EDGAR; refusing, not imputing)")

    def _snapshot(self, symbol: str, metric: str) -> FundamentalPoint | None:
        try:
            import yfinance as yf  # type: ignore
            info: dict[str, Any] = yf.Ticker(symbol).info or {}
        except Exception:
            return None
        keymap = {"pe": "trailingPE", "pb": "priceToBook", "roe": "returnOnEquity",
                  "eps_ttm": "trailingEps", "debt_equity": "debtToEquity"}
        raw = info.get(keymap.get(metric.lower(), metric))
        if raw is None:
            return None
        today = datetime.utcnow().date().isoformat()
        return FundamentalPoint(symbol.upper(), metric.lower(), float(raw),
                               today, today, "yfinance_snapshot")


__all__ = ["FundamentalPoint", "FundamentalsProvider", "FundamentalsUnavailable"]
