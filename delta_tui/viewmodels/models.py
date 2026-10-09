"""Typed viewmodels — the ONLY contract between backend and TUI widgets."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Number:
    value: float
    fmt: str = ".2f"
    source: str = "unknown"
    as_of: str = ""
    confidence: str = "n/a"

    def render(self) -> str:
        try:
            val = format(self.value, self.fmt)
        except Exception:
            val = str(self.value)
        src = (self.source or "").strip() or "unknown"
        if src.lower() in ("unavailable", "unknown", "n/a"):
            return f"UNAVAILABLE [SOURCE/{src}]"
        out = f"{val} [SOURCE/{src}]"
        if self.as_of:
            out += f" [AS-OF {self.as_of}]"
        if self.confidence and str(self.confidence).lower() not in ("n/a", ""):
            out += f" [CONF {self.confidence}]"
        return out


@dataclass(frozen=True)
class QuoteVM:
    symbol: str
    last: Number
    change_pct: float
    bid: float
    ask: float
    bid_sz: int = 0
    ask_sz: int = 0
    vwap: float = 0.0
    mode: str = "PAPER"
    depth_source: str = "unavailable"


@dataclass(frozen=True)
class BookLevel:
    price: float
    size: int


@dataclass(frozen=True)
class BookVM:
    symbol: str
    bids: tuple = ()
    asks: tuple = ()
    imbalance: float = 0.0
    microprice: float = 0.0
    spread_bps: float = 0.0
    mode: str = "PAPER"
    source: str = "unavailable"


@dataclass(frozen=True)
class HomeVM:
    # P-1.2: financials are None (UNAVAILABLE) until a runtime snapshot
    # provides them. Never fabricate splash numbers.
    regime: str = "UNKNOWN"
    liquidity: str = "UNKNOWN"
    net_liq: float | None = None
    gross_pct: float | None = None
    net_pct: float | None = None
    var99: float | None = None
    es99: float | None = None
    drawdown: float | None = None
    opportunities: tuple = ()
    mode: str = "PAPER"


@dataclass(frozen=True)
class RiskVM:
    status: str = "GREEN"
    gross: float | None = None
    gross_lim: float = 200.0
    net: float | None = None
    net_lim: float = 100.0
    var99: float | None = None
    es99: float | None = None
    watches: tuple = ()
    mode: str = "PAPER"
    source: str = "unavailable"


@dataclass(frozen=True)
class ResearchVM:
    experiment_id: str = ""
    hypothesis: str = ""
    stage: str = "planned"
    stages_done: tuple = ()
    ic: float | None = None
    icir: float | None = None
    verdict: str = "PENDING"
    mode: str = "RESEARCH"
    source: str = "unavailable"


@dataclass(frozen=True)
class ExecutionVM:
    parent: str = ""
    algo: str = "VWAP"
    filled: int = 0
    total: int = 0
    venues: tuple = ()
    shortfall_bps: float = 0.0
    mode: str = "PAPER"


@dataclass(frozen=True)
class SystemVM:
    data: tuple = ()
    models: tuple = ()
    brokers: tuple = ()
    events_per_s: float | None = None
    p99_us: float | None = None
    modelled_p99_ms: float | None = None
    compute_p99_ms: float | None = None
    mode: str = "PAPER"
    source: str = "unavailable"


@dataclass(frozen=True)
class MarketVM:
    indices: tuple = ()
    regime: str = "NEUTRAL"
    sectors: tuple = ()
    events: tuple = ()
    mode: str = "PAPER"


@dataclass(frozen=True)
class PortfolioVM:
    net_liq: float | None = None
    cash: float | None = None
    gross_pct: float | None = None
    net_pct: float | None = None
    beta: float | None = None
    positions: tuple = ()
    mode: str = "PAPER"
    live: bool = False  # False => labelled SIMULATION/illustrative
    source: str = "unavailable"
