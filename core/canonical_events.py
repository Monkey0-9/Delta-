"""Phases 54-56 — Canonical events + audit. Every state change: correlation ID.

Market/Quote/Trade/Order/Fill/Risk/Model/Tool/MCP/Broker/Session/Audit events.
TUI subscribes; audit record carries timestamp/session/actor/correlation/
operation/result/provenance/hash (SHA-256 chain in governance/compliance.py).
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone


EVENT_TYPES = ("MarketEvent", "QuoteEvent", "TradeEvent", "OrderEvent",
               "FillEvent", "RiskEvent", "ModelEvent", "ToolEvent",
               "MCPEvent", "BrokerEvent", "SessionEvent", "AuditEvent")


@dataclass(frozen=True)
class Event:
    kind: str
    correlation_id: str
    at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    payload: dict = field(default_factory=dict)

    def __post_init__(self):
        if self.kind not in EVENT_TYPES:
            raise ValueError(f"unknown event {self.kind}")


@dataclass
class AuditRecord:
    timestamp: str
    session: str
    actor: str
    correlation_id: str
    operation: str
    result: str
    provenance: str = ""
    prev_hash: str = ""

    @property
    def hash(self) -> str:
        blob = json.dumps([self.timestamp, self.session, self.actor,
                           self.correlation_id, self.operation, self.result,
                           self.provenance, self.prev_hash],
                          sort_keys=True, default=str).encode()
        return hashlib.sha256(blob).hexdigest()


__all__ = ["EVENT_TYPES", "Event", "AuditRecord"]
