"""Canonical domain model — DELTA interface freeze (P0).

Converges multiple generations (market_data/*, data/feed_abstraction,
core/domain/order, schemas/events) onto ONE canonical path for production.

Every canonical record carries:
  - 7-timestamp provenance (t_observation/event/publication/availability/
    ingestion/decision/execution — subset applicable per record)
  - source/venue, content hash, licensing class, maturity state

Maturity: DESIGNED -> IMPLEMENTED -> TESTED -> PROVEN.
Research grades: UNTESTED -> PROVISIONAL -> VALIDATED -> OOS-VALIDATED
  -> SHADOW-VALIDATED -> CERTIFIED -> RETIRED.

No-LLM rule: VaR/exposure/validation/sizing/limits/dedup/hours/P&L/lifecycle
are deterministic code. LLM explains only.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
import json


class Maturity(str, Enum):
    DESIGNED = "DESIGNED"
    IMPLEMENTED = "IMPLEMENTED"
    TESTED = "TESTED"
    PROVEN = "PROVEN"


class ResearchGrade(str, Enum):
    UNTESTED = "UNTESTED"
    PROVISIONAL = "PROVISIONAL"
    VALIDATED = "VALIDATED"
    OOS_VALIDATED = "OOS-VALIDATED"
    SHADOW_VALIDATED = "SHADOW-VALIDATED"
    CERTIFIED = "CERTIFIED"
    RETIRED = "RETIRED"


class ModelStatus(str, Enum):
    EXPERIMENTAL = "EXPERIMENTAL"
    CANDIDATE = "CANDIDATE"
    SHADOW = "SHADOW"
    CERTIFIED = "CERTIFIED"
    DEPLOYED = "DEPLOYED"
    RETIRED = "RETIRED"
    REJECTED = "REJECTED"


def _utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


@dataclass(frozen=True, slots=True)
class SevenTimestamps:
    """t_observation/event/publication/availability/ingestion/decision/execution.

    Invariant enforced: event <= publication <= availability <= ingestion.
    Decision/execution only on order/execution records.
    A record with asof < availability is lookahead — PIT joins must reject it.
    """
    t_event: datetime
    t_publication: datetime | None = None
    t_availability: datetime | None = None
    t_ingestion: datetime | None = None
    t_observation: datetime | None = None
    t_decision: datetime | None = None
    t_execution: datetime | None = None

    def __post_init__(self) -> None:
        ev = _utc(self.t_event)
        pub = _utc(self.t_publication)
        avl = _utc(self.t_availability)
        ing = _utc(self.t_ingestion)
        object.__setattr__(self, "t_event", ev)
        if pub is not None:
            object.__setattr__(self, "t_publication", pub)
            if pub < ev:
                raise ValueError("t_publication < t_event: time travel")
        if avl is not None:
            object.__setattr__(self, "t_availability", avl)
            anchor = pub if pub is not None else ev
            if avl < anchor:
                raise ValueError("t_availability < publication/event")
        if ing is not None:
            object.__setattr__(self, "t_ingestion", ing)
            if avl is not None and ing < avl:
                raise ValueError("t_ingestion < t_availability")

    def available_at(self) -> datetime:
        return self.t_availability or self.t_publication or self.t_event

    def is_usable_at(self, asof: datetime) -> bool:
        a = asof if asof.tzinfo else asof.replace(tzinfo=timezone.utc)
        return self.available_at() <= a


def content_hash(payload: dict) -> str:
    return sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()[:16]


@dataclass(frozen=True, slots=True)
class CanonicalAsset:
    symbol: str
    asset_class: str  # EQUITY|ETF|OPTION|FUTURE|BOND|FX|COMMODITY|CRYPTO
    currency: str = "USD"
    venue: str = "NYSE"
    maturity: Maturity = Maturity.IMPLEMENTED


@dataclass(frozen=True, slots=True)
class CanonicalQuote:
    asset: CanonicalAsset
    bid: float
    ask: float
    bid_size: int
    ask_size: int
    ts: SevenTimestamps
    sequence: int = 0
    condition: str = ""
    source: str = "unknown"
    license_class: str = "delayed"

    def __post_init__(self) -> None:
        if self.ask < self.bid:
            raise ValueError("crossed quote")
        if self.bid <= 0 or self.ask <= 0:
            raise ValueError("non-positive price")


@dataclass(frozen=True, slots=True)
class CanonicalBar:
    asset: CanonicalAsset
    open: float
    high: float
    low: float
    close: float
    volume: int
    ts: SevenTimestamps
    vendor: str = "unknown"

    def __post_init__(self) -> None:
        if not (self.low <= min(self.open, self.close) <= max(self.open, self.close) <= self.high):
            raise ValueError("OHLC inconsistent")


@dataclass(frozen=True, slots=True)
class CanonicalSignal:
    signal_id: str
    asset: CanonicalAsset
    value: float
    ts: SevenTimestamps
    factor_id: str = ""
    neutralization: tuple[str, ...] = ()
    ic_oos: float | None = None
    grade: ResearchGrade = ResearchGrade.UNTESTED


@dataclass(frozen=True, slots=True)
class CanonicalForecast:
    asset: CanonicalAsset
    mean: float
    variance: float
    quantiles: tuple[tuple[float, float], ...] = ()
    p_positive: float | None = None
    confidence: float | None = None
    ts: SevenTimestamps | None = None
    model_id: str = ""
    calibration_error: float | None = None


@dataclass(frozen=True, slots=True)
class CanonicalPortfolio:
    weights: tuple[tuple[str, float], ...]
    ts: SevenTimestamps | None = None
    gross: float = 0.0
    net: float = 0.0
    turnover: float = 0.0


@dataclass(frozen=True, slots=True)
class CanonicalRiskState:
    var95: float
    var99: float
    cvar99: float
    gross: float
    net: float
    beta: float = 0.0
    ts: SevenTimestamps | None = None
    blocked: bool = False


@dataclass(frozen=True, slots=True)
class CanonicalOrder:
    client_order_id: str
    idempotency_key: str
    symbol: str
    side: str
    quantity: int
    price: float | None = None
    order_type: str = "LIMIT"
    strategy_id: str = ""
    decision_id: str = ""
    parent_order_id: str = ""
    ts: SevenTimestamps | None = None


@dataclass(frozen=True, slots=True)
class CanonicalExecution:
    client_order_id: str
    venue: str
    algorithm: str
    ts: SevenTimestamps | None = None


@dataclass(frozen=True, slots=True)
class CanonicalFill:
    client_order_id: str
    fill_id: str
    quantity: int
    price: float
    venue: str
    ts: SevenTimestamps | None = None


@dataclass(frozen=True, slots=True)
class CanonicalEvidence:
    evidence_id: str
    source: str
    published_at: datetime
    retrieved_at: datetime
    hash: str = ""
    confidence: float | None = None
    authority: str = ""


@dataclass(frozen=True, slots=True)
class CanonicalDecision:
    decision_id: str
    intent: str
    assets: tuple[str, ...]
    mode: str  # RESEARCH|SIMULATION|PAPER|SHADOW|CERTIFIED|LIVE
    authorization: str = ""
    constraints: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class CanonicalExperiment:
    experiment_id: str
    hypothesis: str
    dataset_hash: str
    pit_cutoff: datetime
    parameters: tuple[tuple[str, str], ...] = ()
    grade: ResearchGrade = ResearchGrade.UNTESTED
    git_commit: str = ""
    seed: int = 0


@dataclass(frozen=True, slots=True)
class CanonicalModel:
    model_id: str
    version: str
    dataset_hash: str
    code_version: str
    status: ModelStatus = ModelStatus.EXPERIMENTAL
    calibration_error: float | None = None
    latency_ms_p50: float | None = None


__all__ = [
    "Maturity", "ResearchGrade", "ModelStatus", "SevenTimestamps",
    "content_hash", "CanonicalAsset", "CanonicalQuote", "CanonicalBar",
    "CanonicalSignal", "CanonicalForecast", "CanonicalPortfolio",
    "CanonicalRiskState", "CanonicalOrder", "CanonicalExecution",
    "CanonicalFill", "CanonicalEvidence", "CanonicalDecision",
    "CanonicalExperiment", "CanonicalModel",
]
