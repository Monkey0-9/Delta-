"""Real-time risk monitor: rate, position, loss, kill-switch with audit.

Complements the pre-trade RiskFirewall (per-order checks) with STATEFUL
intraday supervision: orders/minute cap, gross position cap, realized-loss
cap. Any breach TRIPS the shared kill switch and writes a hash-chained audit
record. Monitor never auto-resets: reset() requires an explicit actor +
reason (operations accountability).
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

MON_VERSION = "rtmon-v1"


@dataclass
class TripRecord:
    ts: str
    rule: str
    detail: str
    actor: str
    prev_hash: str
    hash: str = ""


class RealtimeRiskMonitor:
    def __init__(self, max_orders_per_min: int = 60, max_gross_position: float = 1e6,
                 max_day_loss: float = 50_000.0, kill_switch=None) -> None:
        self.max_orders_per_min = max_orders_per_min
        self.max_gross_position = max_gross_position
        self.max_day_loss = max_day_loss
        self._kill = kill_switch
        self._order_ts: list[float] = []
        self._positions: dict[str, float] = {}
        self._realized: float = 0.0
        self._day: str = datetime.now(timezone.utc).date().isoformat()
        self._audit: list[TripRecord] = []
        self._tripped = False

    def _audit_write(self, rule: str, detail: str, actor: str) -> TripRecord:
        prev = self._audit[-1].hash if self._audit else "0" * 64
        rec = TripRecord(datetime.now(timezone.utc).isoformat(), rule, detail,
                         actor, prev)
        rec.hash = hashlib.sha256(json.dumps(
            [rec.ts, rule, detail, actor, prev], separators=(",", ":")).encode()
        ).hexdigest()
        self._audit.append(rec)
        return rec

    def _trip(self, rule: str, detail: str) -> None:
        self._tripped = True
        self._audit_write(rule, detail, actor="monitor")
        if self._kill is not None:
            try:
                self._kill.activate()
            except Exception:
                pass

    @property
    def tripped(self) -> bool:
        return self._tripped

    def on_order(self, now_s: float | None = None) -> bool:
        """Returns True if allowed; trips + returns False on rate breach."""
        now = now_s if now_s is not None else time.time()
        self._order_ts = [t for t in self._order_ts if now - t < 60]
        self._order_ts.append(now)
        if len(self._order_ts) > self.max_orders_per_min:
            self._trip("order_rate", f"{len(self._order_ts)}/min > {self.max_orders_per_min}")
            return False
        return not self._tripped

    def on_fill(self, symbol: str, signed_qty: float, price: float,
                realized_delta: float = 0.0) -> bool:
        self._positions[symbol] = self._positions.get(symbol, 0.0) + signed_qty
        self._realized += realized_delta
        gross = sum(abs(q) * price for q in self._positions.values())
        if gross > self.max_gross_position:
            self._trip("gross_position", f"{gross:,.0f} > {self.max_gross_position:,.0f}")
            return False
        if self._realized < -abs(self.max_day_loss):
            self._trip("day_loss", f"{self._realized:,.0f} < -{self.max_day_loss:,.0f}")
            return False
        return not self._tripped

    def reset(self, actor: str, reason: str) -> None:
        if not actor.strip() or not reason.strip():
            raise ValueError("reset requires actor + reason (no silent restarts).")
        self._tripped = False
        self._order_ts.clear()
        self._audit_write("manual_reset", reason, actor)

    def verify_audit(self) -> bool:
        prev = "0" * 64
        for r in self._audit:
            if r.prev_hash != prev:
                return False
            h = hashlib.sha256(json.dumps(
                [r.ts, r.rule, r.detail, r.actor, r.prev_hash],
                separators=(",", ":")).encode()).hexdigest()
            if h != r.hash:
                return False
            prev = r.hash
        return True

    def status(self) -> dict:
        return {"version": MON_VERSION, "tripped": self._tripped,
                "open_symbols": len(self._positions), "realized": round(self._realized, 2),
                "audit_records": len(self._audit), "audit_ok": self.verify_audit()}


__all__ = ["MON_VERSION", "TripRecord", "RealtimeRiskMonitor"]
