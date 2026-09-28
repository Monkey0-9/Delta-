from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from core.domain.timestamp import ensure_utc, utc_now

EVENT_SCHEMAS: dict[str, tuple[str, ...]] = {
    "quote": ("event_id", "event_time", "received_time", "source", "schema_version"),
    "trade": ("event_id", "event_time", "received_time", "source", "schema_version"),
    "world_state": ("state_id", "version", "timestamp", "hash"),
    "decision": ("decision_id", "model_version", "strategy_version", "world_state_version"),
    "risk_decision": ("risk_decision_id", "limits_version", "decision_id"),
    "order": ("order_id", "idempotency_key", "decision_id", "risk_decision_id"),
    "fill": ("fill_id", "order_id", "executed_at"),
    "l1": ("event_id", "event_time", "as_of", "symbol", "venue"),
    "l2": ("event_id", "event_time", "as_of", "symbol", "venue", "level", "side"),
    "l3": ("event_id", "event_time", "as_of", "symbol", "venue", "order_id", "action"),
}

SCHEMA_VERSION = 2


@dataclass(frozen=True, slots=True)
class PITStamps:
    """W101 PIT foundation: no feature may use info after as_of."""
    as_of: datetime  # decision timestamp; usable_information <= as_of
    publication_time: datetime  # when venue/data published
    ingestion_time: datetime  # when DELTA ingested
    observation_time: datetime  # when observed at source

    def __post_init__(self) -> None:
        for name in ("as_of", "publication_time", "ingestion_time", "observation_time"):
            ensure_utc(getattr(self, name))
        if self.publication_time > self.ingestion_time:
            raise ValueError("publication_time cannot exceed ingestion_time (time travel).")

    def is_usable(self, decision_ts: datetime) -> bool:
        return self.ingestion_time <= ensure_utc(decision_ts) <= self.as_of or self.as_of <= ensure_utc(decision_ts)


@dataclass(frozen=True, slots=True)
class Tick:
    event_id: UUID = field(default_factory=uuid4)
    symbol: str = ""
    venue: str = ""
    price: Decimal = Decimal("0")
    quantity: Decimal = Decimal("0")
    stamps: PITStamps | None = None
    schema_version: int = SCHEMA_VERSION


@dataclass(frozen=True, slots=True)
class Trade:
    event_id: UUID = field(default_factory=uuid4)
    symbol: str = ""
    venue: str = ""
    price: Decimal = Decimal("0")
    quantity: Decimal = Decimal("0")
    side: str = ""  # BUY | SELL | UNKNOWN
    stamps: PITStamps | None = None
    schema_version: int = SCHEMA_VERSION


@dataclass(frozen=True, slots=True)
class Quote:
    event_id: UUID = field(default_factory=uuid4)
    symbol: str = ""
    venue: str = ""
    bid_price: Decimal = Decimal("0")
    bid_quantity: Decimal = Decimal("0")
    ask_price: Decimal = Decimal("0")
    ask_quantity: Decimal = Decimal("0")
    stamps: PITStamps | None = None
    schema_version: int = SCHEMA_VERSION


@dataclass(frozen=True, slots=True)
class NBBO:
    event_id: UUID = field(default_factory=uuid4)
    symbol: str = ""
    bid_price: Decimal = Decimal("0")
    bid_quantity: Decimal = Decimal("0")
    bid_venue: str = ""
    ask_price: Decimal = Decimal("0")
    ask_quantity: Decimal = Decimal("0")
    ask_venue: str = ""
    stamps: PITStamps | None = None
    schema_version: int = SCHEMA_VERSION


@dataclass(frozen=True, slots=True)
class L1Delta:
    event_id: UUID = field(default_factory=uuid4)
    symbol: str = ""
    venue: str = ""
    best_bid: Decimal = Decimal("0")
    best_ask: Decimal = Decimal("0")
    seq: int = 0
    stamps: PITStamps | None = None
    schema_version: int = SCHEMA_VERSION


@dataclass(frozen=True, slots=True)
class L2Delta:
    event_id: UUID = field(default_factory=uuid4)
    symbol: str = ""
    venue: str = ""
    side: str = ""  # BID | ASK
    price: Decimal = Decimal("0")
    quantity: Decimal = Decimal("0")  # 0 = level removal
    level: int = 0
    seq: int = 0
    stamps: PITStamps | None = None
    schema_version: int = SCHEMA_VERSION


@dataclass(frozen=True, slots=True)
class L3OrderEvent:
    event_id: UUID = field(default_factory=uuid4)
    symbol: str = ""
    venue: str = ""
    order_id: str = ""
    action: str = ""  # ADD | CANCEL | REPLACE | FILL | HIDDEN_ADD
    side: str = ""  # BUY | SELL
    price: Decimal = Decimal("0")
    quantity: Decimal = Decimal("0")
    hidden: bool = False
    seq: int = 0
    stamps: PITStamps | None = None
    schema_version: int = SCHEMA_VERSION


@dataclass(frozen=True, slots=True)
class VenueMeta:
    venue: str = ""
    maker_fee_bps: Decimal = Decimal("0")
    taker_fee_bps: Decimal = Decimal("0")
    latency_base_ns: int = 50_000
    reliability: Decimal = Decimal("1")
    schema_version: int = SCHEMA_VERSION
