"""G11 — Canonical market models + freshness + tri-tier router badges + feed health.

Truthful: no fake ticks. Synthetic explicitly badged. Health: HEALTHY/DEGRADED/DOWN.
"""
from __future__ import annotations

from dataclasses import dataclass
from time import time


@dataclass(frozen=True)
class Tick:
    symbol: str
    price: float
    qty: float
    t_event: float
    source: str = "unknown"
    as_of: float = 0.0


@dataclass(frozen=True)
class Quote:
    symbol: str
    bid: float
    ask: float
    t_event: float
    source: str = "unknown"


@dataclass(frozen=True)
class Bar:
    symbol: str
    o: float
    h: float
    l: float
    c: float
    v: float
    t_event: float


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
