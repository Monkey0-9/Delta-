"""Compliance: immutable audit log + best-execution report.

Every order/fill/cancel decision appends a hash-chained record (tamper-evident;
verify() replays the chain). best_execution_report() compares each fill price
against the arrival reference price and flags violations beyond tolerance —
the documentary basis for best-execution review. Records never delete.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone

COMPLIANCE_VERSION = "compliance-v1"


@dataclass
class AuditRecord:
    seq: int
    ts: str
    kind: str  # order|fill|cancel|risk_block|kill|reset|report
    payload: dict
    prev_hash: str
    hash: str = ""


class ComplianceLog:
    def __init__(self) -> None:
        self._records: list[AuditRecord] = []

    def append(self, kind: str, payload: dict) -> AuditRecord:
        if not kind.strip():
            raise ValueError("kind required.")
        prev = self._records[-1].hash if self._records else "0" * 64
        rec = AuditRecord(len(self._records), datetime.now(timezone.utc).isoformat(),
                          kind, dict(payload), prev)
        rec.hash = hashlib.sha256(json.dumps(
            [rec.seq, rec.ts, kind, rec.payload, prev],
            sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()
        self._records.append(rec)
        return rec

    def verify(self) -> bool:
        prev = "0" * 64
        for r in self._records:
            if r.prev_hash != prev:
                return False
            h = hashlib.sha256(json.dumps(
                [r.seq, r.ts, r.kind, r.payload, r.prev_hash],
                sort_keys=True, separators=(",", ":"), default=str).encode()
            ).hexdigest()
            if h != r.hash:
                return False
            prev = r.hash
        return True

    def best_execution_report(self, tolerance_bps: float = 10.0) -> dict:
        """Per-fill slippage vs arrival reference; flags > tolerance."""
        rows, bad = [], 0
        for r in self._records:
            if r.kind != "fill":
                continue
            ref = float(r.payload.get("arrival_px", 0) or 0)
            px = float(r.payload.get("price", 0) or 0)
            side = r.payload.get("side", "buy")
            if ref <= 0 or px <= 0:
                continue
            slip = (px - ref) / ref * 1e4 * (1 if side == "buy" else -1)
            flag = abs(slip) > tolerance_bps
            bad += flag
            rows.append({"order_id": r.payload.get("order_id"), "slip_bps": round(slip, 2),
                         "flag": flag})
        fills = len(rows)
        return {"version": COMPLIANCE_VERSION, "fills": fills,
                "violations": bad,
                "violation_rate": round(bad / fills, 4) if fills else 0.0,
                "tolerance_bps": tolerance_bps, "rows": rows}

    def __len__(self) -> int:
        return len(self._records)


__all__ = ["COMPLIANCE_VERSION", "AuditRecord", "ComplianceLog"]
