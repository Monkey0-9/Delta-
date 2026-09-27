"""W94 real market data: historical + PIT + calendars + corp actions + quality.

Tries Yahoo Finance (yfinance) with short timeout; on any failure uses a
seeded synthetic OHLCV generator labeled source="synthetic_offline".
Both paths produce PIT-safe frames: bar at time t is only usable with
pit_lag applied, and point-in-time reads filter as_of <= t - lag.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

PIT_LAG_MINUTES = 15
FEATURE_VERSION = "features-v2"
DATA_VERSION = "marketdata-v2"


def _seed(sym: str, salt: str) -> int:
    h = hashlib.sha256(f"{sym}:{salt}".encode()).hexdigest()
    return int(h[:8], 16)


@dataclass(frozen=True, slots=True)
class BarSet:
    symbol: str
    frame: pd.DataFrame  # columns: open,high,low,close,volume ; DatetimeIndex UTC
    source: str  # "yahoo" | "synthetic_offline"
    data_hash: str
    pit_lag_minutes: int = PIT_LAG_MINUTES


def _hash_frame(frame: pd.DataFrame) -> str:
    return hashlib.sha256(
        pd.util.hash_pandas_object(frame, index=True).values.tobytes()
    ).hexdigest()[:16]


def synthetic_bars(symbol: str, days: int = 180, seed_salt: str = "w94",
                   end: datetime | None = None) -> BarSet:
    """Seeded geometric-Brownian-motion bars. Deterministic per symbol.

    Regime mix (trend + vol clustering + jumps) so momentum/MR/vol features
    are non-degenerate. Labeled synthetic — never presented as market truth.
    """
    end = end or datetime.now(timezone.utc)
    rng = np.random.default_rng(_seed(symbol, seed_salt))
    n = max(days, 60)
    idx = pd.date_range(end=end, periods=n, freq="B", tz="UTC")
    drift = (rng.random() - 0.48) * 0.0015
    base_vol = 0.008 + rng.random() * 0.014
    rets = rng.normal(drift, base_vol, n)
    # vol clustering + occasional jumps
    for i in range(1, n):
        rets[i] += 0.35 * rets[i - 1] * rng.random()
    jumps = rng.random(n) < 0.02
    rets[jumps] += rng.normal(0, 0.04, jumps.sum())
    px = 40 + (rng.random() * 160)
    closes = px * np.exp(np.cumsum(rets))
    opens = np.concatenate([[px], closes[:-1]]) * (1 + rng.normal(0, 0.001, n))
    highs = np.maximum(opens, closes) * (1 + np.abs(rng.normal(0, 0.003, n)))
    lows = np.minimum(opens, closes) * (1 - np.abs(rng.normal(0, 0.003, n)))
    vols = (500_000 + rng.lognormal(13, 0.7, n)).astype(int)
    frame = pd.DataFrame(
        {"open": opens, "high": highs, "low": lows, "close": closes, "volume": vols},
        index=idx,
    )
    return BarSet(symbol, frame, "synthetic_offline", _hash_frame(frame))


def fetch_bars(symbols: list[str], days: int = 180) -> dict[str, BarSet]:
    """Fetch daily bars; Yahoo first, synthetic fallback per symbol."""
    out: dict[str, BarSet] = {}
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=int(days * 1.6))
    for sym in symbols:
        bars = _try_yahoo(sym, start, end)
        if bars is None:
            bars = synthetic_bars(sym, days=days, end=end)
        out[sym] = bars
    return out


def _try_yahoo(sym: str, start: datetime, end: datetime) -> BarSet | None:
    try:
        import yfinance as yf  # type: ignore

        df = yf.Ticker(sym).history(
            start=start.strftime("%Y-%m-%d"),
            end=end.strftime("%Y-%m-%d"),
            interval="1d",
            auto_adjust=True,
            prepost=False,
        )
        if df is None or df.empty or len(df) < 60:
            return None
        df.columns = [str(c).lower() for c in df.columns]
        cols = {c: c for c in ("open", "high", "low", "close", "volume") if c in df.columns}
        if "close" not in cols:
            return None
        frame = df[list(cols)].copy()
        frame.index = pd.to_datetime(frame.index, utc=True)
        frame = frame.sort_index().dropna()
        if len(frame) < 60:
            return None
        return BarSet(sym, frame, "yahoo", _hash_frame(frame))
    except Exception:
        return None


def pit_slice(bars: BarSet, as_of: datetime, lag_minutes: int = PIT_LAG_MINUTES) -> pd.DataFrame:
    """Point-in-time slice: only bars with timestamp <= as_of - lag."""
    cutoff = pd.Timestamp(as_of).tz_convert("UTC") - pd.Timedelta(minutes=lag_minutes)
    return bars.frame[bars.frame.index <= cutoff]


def data_quality(frame: pd.DataFrame) -> dict:
    """Lightweight quality checks: gaps, stale, outliers, negative prices."""
    issues: list[str] = []
    if frame.empty:
        return {"ok": False, "issues": ["empty"], "coverage": 0.0}
    if (frame[["open", "high", "low", "close"]] <= 0).any().any():
        issues.append("non_positive_price")
    rets = frame["close"].pct_change().dropna()
    if len(rets):
        if (rets.abs() > 0.35).any():
            issues.append("extreme_move_gt35pct")
    # gap detection on business days
    expected = pd.date_range(frame.index[0], frame.index[-1], freq="B", tz="UTC")
    coverage = len(frame.index.intersection(expected)) / max(len(expected), 1)
    if coverage < 0.9:
        issues.append(f"low_coverage_{coverage:.2f}")
    if (frame["volume"] <= 0).mean() > 0.05:
        issues.append("zero_volume_bars")
    return {"ok": not issues, "issues": issues, "coverage": round(float(coverage), 4)}


@dataclass
class CorporateActionLog:
    """Splits/dividends applied to bars (auto_adjust covers Yahoo; synthetic none)."""

    splits: dict = field(default_factory=dict)
    dividends: dict = field(default_factory=dict)
