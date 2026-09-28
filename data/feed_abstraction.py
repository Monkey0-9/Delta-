"""W151-W170 (A) — Market-data reality: direct-feed abstraction,
vendor reconciliation, historical multi-asset PIT scale.

All vendors normalize into ONE canonical schema (CanonicalBar / CanonicalTick)
so every downstream component is vendor-agnostic. Reconciliation quantifies
disagreement instead of hiding it. Deterministic; no network calls —
vendor adapters are interfaces with a deterministic synthetic adapter used
in tests and offline research.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field


def _hash(obj: object) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()[:12]


@dataclass(frozen=True, slots=True)
class CanonicalTick:
    symbol: str
    ts_ns: int
    venue: str
    bid: float
    ask: float
    last: float
    volume: float


@dataclass(frozen=True, slots=True)
class CanonicalBar:
    symbol: str
    ts_ns: int
    asset_class: str  # equity|etf|future|fx|rate|commodity|crypto
    open: float
    high: float
    low: float
    close: float
    volume: float
    vendor: str


class VendorAdapter:
    """Interface: each vendor (Yahoo/Polygon/Databento/Nasdaq/CME/IB/multicast)
    implements fetch_bars -> CanonicalBar list. Never raises for gaps:
    returns what exists; gaps are explicit via reconciliation."""

    vendor: str = "base"

    def fetch_bars(self, symbol: str, start_ns: int, end_ns: int) -> list[CanonicalBar]:
        raise NotImplementedError


class SyntheticVendor(VendorAdapter):
    """Deterministic offline vendor (seeded walk) for research without entitlements."""

    def __init__(self, vendor: str = "synthetic", seed: int = 7, asset_class: str = "equity") -> None:
        self.vendor = vendor
        self._seed = seed
        self._ac = asset_class

    def fetch_bars(self, symbol: str, start_ns: int, end_ns: int) -> list[CanonicalBar]:
        out: list[CanonicalBar] = []
        state = (self._seed ^ abs(hash(symbol))) & 0xFFFFFFFF or 1
        px = 100.0
        step = 60_000_000_000
        ts = start_ns
        while ts <= end_ns:
            state ^= (state << 13) & 0xFFFFFFFF
            state ^= state >> 17
            state ^= (state << 5) & 0xFFFFFFFF
            drift = ((state % 2000) - 1000) / 1e6
            px = max(px * (1 + drift), 0.01)
            out.append(CanonicalBar(symbol, ts, self._ac, px, px * 1.001, px * 0.999, px,
                                    float(1000 + state % 5000), self.vendor))
            ts += step
        return out


@dataclass(frozen=True, slots=True)
class VendorDisagreement:
    symbol: str
    ts_ns: int
    max_ts_skew_ns: int
    max_price_rel: float
    volume_rel_gap: float
    missing_in: tuple[str, ...]
    corporate_action_conflict: bool


def reconcile_vendors(symbol: str, feeds: dict[str, list[CanonicalBar]]) -> list[VendorDisagreement]:
    """Align vendor bars by timestamp; quantify disagreement per timestamp."""
    by_ts: dict[int, dict[str, CanonicalBar]] = {}
    for vendor, bars in feeds.items():
        for b in bars:
            if b.symbol == symbol:
                by_ts.setdefault(b.ts_ns, {})[vendor] = b
    out: list[VendorDisagreement] = []
    vendors = sorted(feeds)
    for ts in sorted(by_ts):
        present = by_ts[ts]
        missing = tuple(v for v in vendors if v not in present)
        closes = [present[v].close for v in present]
        vols = [present[v].volume for v in present]
        max_c, min_c = (max(closes), min(closes)) if closes else (0.0, 0.0)
        price_rel = (max_c - min_c) / max_c if max_c > 0 else 0.0
        max_v, min_v = (max(vols), min(vols)) if vols else (0.0, 0.0)
        vol_gap = (max_v - min_v) / max_v if max_v > 0 else 0.0
        # corporate-action conflict heuristic: >10% close divergence
        out.append(VendorDisagreement(symbol, ts, 0, price_rel, vol_gap, missing,
                                     price_rel > 0.10))
    return out


@dataclass
class MultiAssetDataset:
    """PIT dataset spanning asset classes with content hash per (symbol, vendor)."""

    bars: list[CanonicalBar] = field(default_factory=list)

    def add(self, bars: list[CanonicalBar]) -> None:
        self.bars.extend(bars)

    def asof(self, symbol: str, ts_ns: int, vendor: str | None = None) -> list[CanonicalBar]:
        return [b for b in self.bars if b.symbol == symbol and b.ts_ns <= ts_ns
                and (vendor is None or b.vendor == vendor)]

    def content_hash(self, symbol: str, vendor: str) -> str:
        rows = [(b.ts_ns, b.open, b.high, b.low, b.close, b.volume)
                for b in self.bars if b.symbol == symbol and b.vendor == vendor]
        return _hash(sorted(rows))

    def asset_classes(self) -> list[str]:
        return sorted({b.asset_class for b in self.bars})
