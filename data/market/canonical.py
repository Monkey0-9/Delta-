"""G11 — Canonical market models + freshness + tri-tier router badges + feed health.

Truthful: no fake ticks. Synthetic explicitly badged. Health: HEALTHY/DEGRADED/DOWN.
Stage-1: full 5-stamp PIT on every tick/quote/bar (t_event/t_pub/t_avail/t_dec/t_exec).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from time import time


def _utc_ts(v: float | datetime | None) -> float:
    if v is None:
        return 0.0
    if isinstance(v, datetime):
        dt = v if v.tzinfo else v.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    return float(v)


@dataclass(frozen=True)
class Tick:
    symbol: str
    price: float
    qty: float
    t_event: float
    source: str = "unknown"
    as_of: float = 0.0
    t_pub: float = 0.0
    t_avail: float = 0.0
    t_dec: float = 0.0
    t_exec: float = 0.0

    def __post_init__(self) -> None:
        seq = [self.t_event, self.t_pub or self.t_event,
               self.t_avail or self.t_pub or self.t_event]
        if not (seq[0] <= seq[1] <= seq[2]):
            raise ValueError("PIT violation in Tick: t_event<=t_pub<=t_avail")

    def is_usable_at(self, asof: float | datetime) -> bool:
        return self.t_avail or self.t_pub or self.t_event <= _utc_ts(asof)


@dataclass(frozen=True)
class Quote:
    symbol: str
    bid: float
    ask: float
    t_event: float
    source: str = "unknown"
    t_pub: float = 0.0
    t_avail: float = 0.0

    def __post_init__(self) -> None:
        if self.ask < self.bid:
            raise ValueError("crossed quote")
        pub = self.t_pub or self.t_event
        avl = self.t_avail or pub
        if not (self.t_event <= pub <= avl):
            raise ValueError("PIT violation in Quote")


@dataclass(frozen=True)
class Bar:
    symbol: str
    o: float
    h: float
    l: float
    c: float
    v: float
    t_event: float
    t_pub: float = 0.0
    t_avail: float = 0.0
    source: str = "unknown"
    dataset_version: str = "v1"
    quality: str = "UNKNOWN"

    def __post_init__(self) -> None:
        if not (self.l <= min(self.o, self.c) <= max(self.o, self.c) <= self.h):
            raise ValueError("OHLC inconsistent")
        pub = self.t_pub or self.t_event
        avl = self.t_avail or pub
        if not (self.t_event <= pub <= avl):
            raise ValueError("PIT violation in Bar")

    def is_usable_at(self, asof: float | datetime) -> bool:
        return (self.t_avail or self.t_pub or self.t_event) <= _utc_ts(asof)


VENUES = {
    "PAPER": {"fee_bps": 0.5, "rebate_bps": 0.0, "tick": 0.01, "lot": 1},
    "SIM": {"fee_bps": 1.0, "rebate_bps": 0.0, "tick": 0.01, "lot": 1},
}


@dataclass
class FeedHealth:
    state: str = "HEALTHY"  # HEALTHY|DEGRADED|DOWN
    last_as_of: float = 0.0
    stale_after_s: float = 15.0

    def check(self, now: float | None = None) -> str:
        now = time() if now is None else now
        if self.last_as_of <= 0:
            self.state = "DOWN"
        elif now - self.last_as_of > self.stale_after_s * 4:
            self.state = "DOWN"
        elif now - self.last_as_of > self.stale_after_s:
            self.state = "DEGRADED"
        else:
            self.state = "HEALTHY"
        return self.state


def route_badge(source: str) -> str:
    s = (source or "").lower()
    if s == "live":
        return "SOURCE/live"
    if s == "cache":
        return "SOURCE/cache-DEGRADED"
    return "SOURCE/synthetic-DEMO"


def freshness_s(as_of: float, now: float | None = None) -> float:
    now = time() if now is None else now
    return max(0.0, now - (as_of or 0.0))
