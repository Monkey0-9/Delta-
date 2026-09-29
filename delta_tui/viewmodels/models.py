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
            return format(self.value, self.fmt)
        except Exception:
            return str(self.value)


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


@dataclass(frozen=True)
class HomeVM:
    regime: str = "NEUTRAL"
    liquidity: str = "NORMAL"
    net_liq: float = 0.0
    gross_pct: float = 0.0
    net_pct: float = 0.0
    var99: float = 0.0
    es99: float = 0.0
    drawdown: float = 0.0
    opportunities: tuple = ()
    mode: str = "PAPER"


@dataclass(frozen=True)
class RiskVM:
    status: str = "GREEN"
    gross: float = 0.0
    gross_lim: float = 200.0
    net: float = 0.0
    net_lim: float = 100.0
    var99: float = 0.0
    es99: float = 0.0
    watches: tuple = ()
    mode: str = "PAPER"


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
    events_per_s: float = 0.0
    p99_us: float = 0.0
    modelled_p99_ms: float = 0.0
    compute_p99_ms: float = 0.0
    mode: str = "PAPER"


@dataclass(frozen=True)
class MarketVM:
    indices: tuple = ()
    regime: str = "NEUTRAL"
    sectors: tuple = ()
    events: tuple = ()
    mode: str = "PAPER"


@dataclass(frozen=True)
class PortfolioVM:
    net_liq: float = 0.0
    cash: float = 0.0
    gross_pct: float = 0.0
    net_pct: float = 0.0
    beta: float = 0.0
    positions: tuple = ()
    mode: str = "PAPER"
    live: bool = False  # False => labelled SIMULATION/illustrative
