"""Phase 2 (code part): versioned dataset abstraction for the daily-bar path.

A Dataset binds, under one fingerprint:
  universe + as-of range + per-symbol source/data_hash + calendar version +
  quality report + PIT lag + code/data versions.

Datasets persist to a JSONL registry; verify() recomputes the fingerprint
from the stored fields so tampering or silent substitution is detected.
This is the link between the real_loop research path and the tick_pit
PIT infrastructure (same calendar, same hash discipline).
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path

from research.real_loop import market_data as M

DS_VERSION = "dataset-v1"
REGISTRY_DEFAULT = "artifacts/datasets/registry.jsonl"


@dataclass(frozen=True, slots=True)
class Dataset:
    dataset_id: str
    symbols: tuple[str, ...]
    start: str
    end: str
    bars_days: int
    pit_lag_minutes: int
    calendar_version: str
    per_symbol: tuple  # ((symbol, source, data_hash, coverage, issues), ...)
    universe_hash: str
    fingerprint: str

    def verify(self) -> bool:
        return self.fingerprint == _fingerprint(
            self.symbols, self.start, self.end, self.bars_days,
            self.pit_lag_minutes, self.calendar_version, self.per_symbol,
            self.universe_hash)


def _fingerprint(symbols, start, end, days, lag, calver, per_symbol, uhash) -> str:
    raw = json.dumps({"s": list(symbols), "a": start, "b": end, "d": days,
                      "lag": lag, "cal": calver, "per": [list(p) for p in per_symbol],
                      "u": uhash}, sort_keys=True, default=str)
    return "DS-" + hashlib.sha256(raw.encode()).hexdigest()[:12].upper()


def _calendar():
    try:
        from data.tick_pit.trading_calendar import get_calendar

        return get_calendar("XNYS")
    except Exception:
        return None


def build_dataset(symbols: list[str], days: int = 300,
                  dataset_id: str = "") -> tuple[Dataset, dict]:
    """Fetch bars (fail-closed LIVE rules apply) + quality + fingerprint.

    Returns (Dataset, {symbol: BarSet}). Raises MarketDataUnavailable in LIVE
    when any symbol has no real feed — datasets never silently substitute.
    """
    syms = sorted(set(symbols))
    if not syms:
        raise ValueError("universe must be non-empty.")
    bars = M.fetch_bars(syms, days=days)
    if M.is_simulation():
        pass
    else:
        bad = sorted(s for s, b in bars.items() if b.source != "yahoo")
        if bad:
            raise M.MarketDataUnavailable(f"non-market bars in LIVE: {bad}.")
    cal = _calendar()
    per = []
    for s in syms:
        q = M.data_quality(bars[s].frame, calendar=cal)
        per.append((s, bars[s].source, bars[s].data_hash, q["coverage"],
                    ",".join(q["issues"]) or "OK"))
    starts = min(b.frame.index[0] for b in bars.values()).isoformat()
    ends = max(b.frame.index[-1] for b in bars.values()).isoformat()
    uhash = hashlib.sha256(",".join(
        f"{s}:{bars[s].data_hash}" for s in syms).encode()).hexdigest()[:12]
    calver = getattr(cal, "version", "business-day") if cal else "business-day"
    ds_id = dataset_id or f"DS-{time.strftime('%Y%m%d')}-{uhash.upper()}"
    per_t = tuple(per)
    ds = Dataset(ds_id, tuple(syms), starts, ends, days, M.PIT_LAG_MINUTES,
                 calver, per_t, uhash,
                 _fingerprint(tuple(syms), starts, ends, days, M.PIT_LAG_MINUTES,
                              calver, per_t, uhash))
    assert ds.verify()
    return ds, bars


def save(ds: Dataset, registry: str = REGISTRY_DEFAULT) -> Path:
    p = Path(registry)
    p.parent.mkdir(parents=True, exist_ok=True)
    rec = {"dataset_id": ds.dataset_id, "symbols": list(ds.symbols),
           "start": ds.start, "end": ds.end, "bars_days": ds.bars_days,
           "pit_lag_minutes": ds.pit_lag_minutes,
           "calendar_version": ds.calendar_version,
           "per_symbol": [list(x) for x in ds.per_symbol],
           "universe_hash": ds.universe_hash, "fingerprint": ds.fingerprint,
           "ds_version": DS_VERSION, "t": time.time()}
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, sort_keys=True) + "\n")
    return p


def load(dataset_id: str, registry: str = REGISTRY_DEFAULT) -> Dataset:
    p = Path(registry)
    if not p.exists():
        raise ValueError("dataset registry empty.")
    for line in p.read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        if r["dataset_id"] == dataset_id:
            ds = Dataset(r["dataset_id"], tuple(r["symbols"]), r["start"], r["end"],
                         r["bars_days"], r["pit_lag_minutes"], r["calendar_version"],
                         tuple(tuple(x) for x in r["per_symbol"]),
                         r["universe_hash"], r["fingerprint"])
            if not ds.verify():
                raise ValueError(f"dataset {dataset_id} FAILED verification.")
            return ds
    raise ValueError(f"dataset {dataset_id} not found.")


__all__ = ["DS_VERSION", "Dataset", "build_dataset", "save", "load"]
