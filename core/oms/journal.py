"""Stage-3 Z+1: OMS write-ahead journal — kill-9 → replay → snapshot → reconcile.

Append-only JSONL journal: CREATED→VALIDATED→RISK_APPROVED→SUBMITTED→
ACKNOWLEDGED→FILLED (+CANCELLED/REJECTED). Replay rebuilds state after kill-9.
RTO<60s / RPO=0 design: fsync per append, snapshot + broker-poll hooks.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from threading import Lock
import json
import os

TERMINAL = {"FILLED", "CANCELLED", "REJECTED"}
VALID_NEXT: dict[str, set[str]] = {
    "CREATED": {"VALIDATED", "REJECTED"},
    "VALIDATED": {"RISK_APPROVED", "REJECTED"},
    "RISK_APPROVED": {"SUBMITTED", "CANCELLED"},
    # B9 DR: a SUBMITTED order the broker never saw (crash landed between
    # journal-append and broker-send) never reached the venue — recovery
    # cancels it in-journal. REJECTED would imply venue action; CANCELLED
    # is the truthful state.
    # PRECONDITION on SUBMITTED→CANCELLED: valid ONLY when the broker never
    # saw the order (venue-absent, attested by the recovery path polling the
    # broker book first) — never as a live cancel of a venue-held order.
    # Recovery procedure: scripts/dr_drill.py Phase 3 (broker poll, then
    # catch-up append). Direct appends of this edge outside recovery are a
    # state-machine misuse; treat unexpected CANCELLED-from-SUBMITTED as
    # audit findings, not normal flow.
    "SUBMITTED": {"ACKNOWLEDGED", "REJECTED", "CANCELLED"},
    "ACKNOWLEDGED": {"FILLED", "CANCELLED"},
}


class JournalCorruption(Exception):
    """Raised when replay detects tampering, gaps, torn writes, or
    illegal transitions. Never silently ignored."""


@dataclass(frozen=True, slots=True)
class JournalEntry:
    seq: int
    order_id: str
    state: str
    at: str
    prev_hash: str
    hash: str


def _hash(seq: int, order_id: str, state: str, at: str, prev: str) -> str:
    # Full-length SHA-256 hex. Pre-P0-5 records stored 16-char prefixes;
    # replay verifies those against the truncated recomputation and flags
    # the journal legacy (see OmsJournal.legacy_hashes). New records are
    # always full length.
    return sha256(f"{seq}|{order_id}|{state}|{at}|{prev}".encode()).hexdigest()


def _check_transition(states: dict[str, str], order_id: str, state: str) -> None:
    """Shared transition guard used by both append and replay."""
    cur = states.get(order_id)
    if cur in TERMINAL:
        raise ValueError(f"terminal order {order_id} cannot transition from {cur}")
    if cur is not None and state not in VALID_NEXT.get(cur, set()):
        raise ValueError(f"illegal OMS transition {cur}→{state}")
    if cur is None and state != "CREATED":
        raise ValueError(f"first state must be CREATED, got {state}")


class OmsJournal:
    # Durable-write semantics: every append is followed by flush + os.fsync,
    # so a record is crash-safe once append() returns (RPO=0 for acknowledged
    # appends). Cost: one fsync per append; acceptable for an order journal,
    # never for a hot market-data path.
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        self._seq = 0
        self._prev = "GENESIS"
        self._states: dict[str, str] = {}
        self.legacy_hashes = False
        if self.path.exists():
            self.replay()

    def append(self, order_id: str, state: str) -> JournalEntry:
        with self._lock:
            _check_transition(self._states, order_id, state)
            self._seq += 1
            at = datetime.now(timezone.utc).isoformat()
            h = _hash(self._seq, order_id, state, at, self._prev)
            e = JournalEntry(seq=self._seq, order_id=order_id, state=state,
                             at=at, prev_hash=self._prev, hash=h)
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(json.dumps({"seq": e.seq, "order_id": e.order_id,
                                    "state": e.state, "at": e.at,
                                    "prev_hash": e.prev_hash, "hash": e.hash}) + "\n")
                f.flush()
                os.fsync(f.fileno())
            self._prev = h
            self._states[order_id] = state
            return e

    def replay(self) -> dict[str, str]:
        states: dict[str, str] = {}
        seq = 0
        prev_link = "GENESIS"
        legacy = False
        try:
            with open(self.path, encoding="utf-8") as f:
                raw = f.read()
        except FileNotFoundError:
            self._states, self._seq, self._prev = {}, 0, "GENESIS"
            return {}
        if raw.strip() == "":
            self._states, self._seq, self._prev = {}, 0, "GENESIS"
            return {}
        # A torn tail (crash mid-write) must be refused loudly, never
        # silently dropped: the file must end with a newline and every
        # line must parse.
        if not raw.endswith("\n"):
            raise JournalCorruption(
                f"{self.path}: torn trailing write (missing newline)")
        for lineno, line in enumerate(raw.split("\n")[:-1], start=1):
            if not line.strip():
                raise JournalCorruption(
                    f"{self.path}:{lineno}: blank line breaks the chain")
            try:
                d = json.loads(line)
            except json.JSONDecodeError as exc:
                raise JournalCorruption(
                    f"{self.path}:{lineno}: unparsable record: {exc}") from exc
            for key in ("seq", "order_id", "state", "at", "prev_hash", "hash"):
                if key not in d:
                    raise JournalCorruption(
                        f"{self.path}:{lineno}: missing field {key!r}")
            if d["seq"] != seq + 1:
                raise JournalCorruption(
                    f"{self.path}:{lineno}: sequence gap "
                    f"(expected {seq + 1}, got {d['seq']})")
            if d["prev_hash"] != prev_link:
                raise JournalCorruption(
                    f"{self.path}:{lineno}: hash-chain link broken")
            full = _hash(d["seq"], d["order_id"], d["state"], d["at"],
                         d["prev_hash"])
            stored = d["hash"]
            if len(stored) == 64:
                if stored != full:
                    raise JournalCorruption(
                        f"{self.path}:{lineno}: record hash mismatch (tamper)")
            elif len(stored) == 16 and stored == full[:16]:
                legacy = True  # pre-P0-5 truncated record, link still valid
            else:
                raise JournalCorruption(
                    f"{self.path}:{lineno}: record hash mismatch (tamper)")
            try:
                _check_transition(states, d["order_id"], d["state"])
            except ValueError as exc:
                raise JournalCorruption(
                    f"{self.path}:{lineno}: illegal transition: {exc}") from exc
            states[d["order_id"]] = d["state"]
            seq, prev_link = d["seq"], stored
        with self._lock:
            self._states, self._seq = states, seq
            # Canonical chain head is the full hash of the last record, so a
            # mixed journal (legacy prefix + new full-length records) keeps a
            # single strong head even though legacy links stay 16-char.
            self._prev = full
            self.legacy_hashes = legacy
        return dict(states)

    def snapshot(self) -> dict[str, str]:
        return dict(self._states)


__all__ = ["OmsJournal", "JournalEntry", "JournalCorruption",
           "TERMINAL", "VALID_NEXT"]
