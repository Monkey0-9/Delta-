"""Alpaca-style order-update stream tracker (P0-6, keyless-safe).

Consumes trade-update events in the Alpaca lifecycle vocabulary
(new/partial_fill/fill/canceled/expired/replaced/rejected) and maintains
per-order state. The same tracker consumes the real Alpaca WebSocket later;
today it is proven against a deterministic simulated paper feed, so no API
keys or network are required.

Fail-closed rules:
- duplicate event_id -> ignored, counted (idempotent replay safe)
- stale seq (seq < last_seq) -> ignored as late, counted
- event for unknown order -> recorded as orphan, never creates a position
- transition out of a terminal state (fill/canceled/expired/rejected) ->
  anomaly recorded, terminal state preserved (a late fill after cancel must
  never resurrect size)
- disconnect gaps -> orders flagged NEEDS_RECONCILE until broker positions
  are re-fetched (reconciliation is authoritative, not the stream)
"""
from __future__ import annotations

from dataclasses import dataclass, field

TERMINAL = frozenset({"filled", "canceled", "expired", "rejected"})
ACTIVE = frozenset({"new", "partially_filled", "replaced"})

_EVENT_TO_STATUS = {
    "new": "new",
    "partial_fill": "partially_filled",
    "fill": "filled",
    "canceled": "canceled",
    "expired": "expired",
    "replaced": "replaced",
    "rejected": "rejected",
}


@dataclass
class TrackedOrder:
    client_order_id: str
    status: str = "new"
    filled_qty: float = 0.0
    last_seq: int = 0
    needs_reconcile: bool = False


@dataclass
class StreamStats:
    applied: int = 0
    duplicates: int = 0
    late: int = 0
    orphans: int = 0
    anomalies: int = 0


@dataclass
class OrderStreamTracker:
    orders: dict[str, TrackedOrder] = field(default_factory=dict)
    seen_event_ids: set[str] = field(default_factory=set)
    stats: StreamStats = field(default_factory=StreamStats)
    anomalies: list[str] = field(default_factory=list)

    def register(self, client_order_id: str) -> TrackedOrder:
        o = self.orders.get(client_order_id)
        if o is None:
            o = TrackedOrder(client_order_id)
            self.orders[client_order_id] = o
        return o

    def apply(self, event: dict) -> str:
        """Apply one trade-update event. Returns disposition string."""
        eid = str(event.get("event_id", ""))
        if eid and eid in self.seen_event_ids:
            self.stats.duplicates += 1
            return "duplicate_ignored"
        if eid:
            self.seen_event_ids.add(eid)
        oid = str(event.get("client_order_id", ""))
        o = self.orders.get(oid)
        if o is None:
            self.stats.orphans += 1
            self.anomalies.append(f"orphan:{oid}")
            return "orphan_recorded"
        seq = int(event.get("seq", 0))
        if seq < o.last_seq:
            self.stats.late += 1
            return "late_ignored"
        etype = str(event.get("event", ""))
        if etype not in _EVENT_TO_STATUS:
            self.stats.anomalies += 1
            self.anomalies.append(f"unknown_event:{etype}")
            return "unknown_event"
        if o.status in TERMINAL:
            self.stats.anomalies += 1
            self.anomalies.append(f"terminal_violation:{oid}:{o.status}->{etype}")
            return "terminal_preserved"
        o.status = _EVENT_TO_STATUS[etype]
        try:
            o.filled_qty = max(o.filled_qty, float(event.get("filled_qty", o.filled_qty)))
        except (TypeError, ValueError):
            pass
        o.last_seq = max(o.last_seq, seq)
        self.stats.applied += 1
        return f"applied:{o.status}"

    def note_disconnect(self) -> list[str]:
        """Flag all non-terminal orders for reconciliation after a feed gap."""
        flagged = [oid for oid, o in self.orders.items() if o.status not in TERMINAL]
        for oid in flagged:
            self.orders[oid].needs_reconcile = True
        return flagged

    def clear_reconcile(self, client_order_id: str) -> None:
        if client_order_id in self.orders:
            self.orders[client_order_id].needs_reconcile = False


def simulate_paper_feed(client_order_id: str, qty: float = 100.0) -> list[dict]:
    """Deterministic paper feed: new -> partial -> duplicate partial ->
    late-stale partial -> fill -> late fill-after-terminal, exercising every
    guard without network."""
    half = qty / 2
    return [
        {"event_id": "e1", "seq": 1, "client_order_id": client_order_id,
         "event": "new", "filled_qty": 0.0},
        {"event_id": "e2", "seq": 2, "client_order_id": client_order_id,
         "event": "partial_fill", "filled_qty": half},
        {"event_id": "e2", "seq": 2, "client_order_id": client_order_id,
         "event": "partial_fill", "filled_qty": half},  # duplicate
        {"event_id": "e2b", "seq": 1, "client_order_id": client_order_id,
         "event": "partial_fill", "filled_qty": half},  # stale seq
        {"event_id": "e3", "seq": 3, "client_order_id": client_order_id,
         "event": "fill", "filled_qty": qty},
        {"event_id": "e4", "seq": 4, "client_order_id": client_order_id,
         "event": "fill", "filled_qty": qty},  # post-terminal: anomaly
    ]


__all__ = ["OrderStreamTracker", "TrackedOrder", "StreamStats",
           "simulate_paper_feed", "TERMINAL", "ACTIVE"]
