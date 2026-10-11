"""Compliance: immutable audit log + best-execution report.

Every order/fill/cancel decision appends a hash-chained record (tamper-evident;
verify() replays the chain). best_execution_report() compares each fill price
against the arrival reference price and flags violations beyond tolerance —
the documentary basis for best-execution review. Records never delete.

Durability (P1): with a file path, every append persists as JSONL
(flush+fsync) and construction reloads + verifies the existing file. A
process restart no longer wipes the chain. Without a path the log stays
in-memory (tests, read-only screens).
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from provenance.audit.chain import AuditChain

COMPLIANCE_VERSION = "compliance-v1"


@dataclass
class AuditRecord:
    seq: int
    ts: str
    kind: str  # order|fill|cancel|risk_block|kill|reset|report
    payload: dict
    prev_hash: str
    hash: str = ""


class ComplianceTamperError(Exception):
    """Persisted compliance chain failed verification on load."""


class ComplianceLog:
    """Hash-chained compliance log.

    The local record list is the store of record; every append is mirrored
    into the canonical :class:`provenance.audit.chain.AuditChain` (single
    chain implementation shared with core.audit). verify() requires both
    the local replay and the canonical chain to agree.
    """

    def __init__(self, path: str | Path | None = None) -> None:
        self._records: list[AuditRecord] = []
        self._chain = AuditChain()
        self._path = Path(path) if path is not None else None
        if self._path is not None and self._path.exists():
            self._load()

    def append(self, kind: str, payload: dict) -> AuditRecord:
        if not kind.strip():
            raise ValueError("kind required.")
        prev = self._records[-1].hash if self._records else "0" * 64
        rec = AuditRecord(len(self._records), datetime.now(timezone.utc).isoformat(),
                          kind, dict(payload), prev)
        rec.hash = hashlib.sha256(json.dumps(
            [rec.seq, rec.ts, kind, rec.payload, prev],
            sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()
        # Mirror-then-local: a canonical-chain failure leaves zero local
        # state, so the two can never permanently diverge.
        self._chain.append(record_type=kind, record_id=str(rec.seq),
                           payload_hash=rec.hash)
        self._records.append(rec)
        if self._path is not None:
            self._persist(rec)
        return rec

    def _persist(self, rec: AuditRecord) -> None:
        assert self._path is not None
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._path, "a", encoding="utf-8") as f:
            f.write(json.dumps({"seq": rec.seq, "ts": rec.ts, "kind": rec.kind,
                                "payload": rec.payload, "prev_hash": rec.prev_hash,
                                "hash": rec.hash},
                               sort_keys=True, separators=(",", ":"),
                               default=str) + "\n")
            f.flush()
            os.fsync(f.fileno())

    def _load(self) -> None:
        """Reload a persisted chain; refuse loudly on any corruption.

        A corrupt file is moved to a timestamped backup (evidence preserved,
        never wiped) and loading raises ComplianceTamperError.
        """
        assert self._path is not None

        def _corrupt(reason: str) -> None:
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            backup = self._path.with_name(f"{self._path.name}.corrupt-{stamp}")
            try:
                os.replace(self._path, backup)
            except OSError:
                backup = self._path
            raise ComplianceTamperError(
                f"{self._path}: {reason} (preserved at {backup})")

        raw = self._path.read_text(encoding="utf-8")
        if raw.strip() == "":
            return  # existing but empty file: valid empty chain
        if not raw.endswith("\n"):
            _corrupt("torn trailing write")
        records: list[AuditRecord] = []
        for lineno, line in enumerate(raw.split("\n")[:-1], start=1):
            if not line.strip():
                _corrupt(f"blank line {lineno}")
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                _corrupt(f"unparsable record line {lineno}")
            for key in ("seq", "ts", "kind", "payload", "prev_hash", "hash"):
                if key not in d:
                    _corrupt(f"record line {lineno} missing {key!r}")
            if d["seq"] != len(records):
                _corrupt(f"record line {lineno} sequence gap")
            expected_prev = records[-1].hash if records else "0" * 64
            if d["prev_hash"] != expected_prev:
                _corrupt(f"record line {lineno} chain link broken")
            h = hashlib.sha256(json.dumps(
                [d["seq"], d["ts"], d["kind"], d["payload"], d["prev_hash"]],
                sort_keys=True, separators=(",", ":"), default=str).encode()
            ).hexdigest()
            if h != d["hash"]:
                _corrupt(f"record line {lineno} hash mismatch (tamper)")
            rec = AuditRecord(d["seq"], d["ts"], d["kind"], d["payload"],
                              d["prev_hash"], d["hash"])
            records.append(rec)
            self._chain.append(record_type=rec.kind, record_id=str(rec.seq),
                               payload_hash=rec.hash,
                               timestamp=datetime.fromisoformat(rec.ts))
        self._records = records
        if not self.verify():
            _corrupt("post-load verification failed")

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
        return self._chain.verify()

    def best_execution_report(self, tolerance_bps: float = 10.0) -> dict:
        """Per-fill slippage vs arrival reference; flags > tolerance.

        Fills missing arrival_px/price are FLAGGED rows (never silently
        skipped) so gaps in best-execution evidence stay visible.
        """
        rows, bad = [], 0
        for r in self._records:
            if r.kind != "fill":
                continue
            ref = float(r.payload.get("arrival_px", 0) or 0)
            px = float(r.payload.get("price", 0) or 0)
            side = r.payload.get("side", "buy")
            if ref <= 0 or px <= 0:
                rows.append({"order_id": r.payload.get("order_id"),
                             "slip_bps": None, "flag": True,
                             "reason": "missing_arrival_or_price"})
                bad += 1
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


__all__ = ["COMPLIANCE_VERSION", "AuditRecord", "ComplianceLog",
           "ComplianceTamperError"]
