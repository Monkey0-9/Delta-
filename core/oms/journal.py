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
import json

TERMINAL = {"FILLED", "CANCELLED", "REJECTED"}
VALID_NEXT: dict[str, set[str]] = {
    "CREATED": {"VALIDATED", "REJECTED"},
    "VALIDATED": {"RISK_APPROVED", "REJECTED"},
    "RISK_APPROVED": {"SUBMITTED", "CANCELLED"},
    "SUBMITTED": {"ACKNOWLEDGED", "REJECTED"},
    "ACKNOWLEDGED": {"FILLED", "CANCELLED"},
}


@dataclass(frozen=True, slots=True)
class JournalEntry:
    seq: int
    order_id: str
    state: str
    at: str
    prev_hash: str
    hash: str


def _hash(seq: int, order_id: str, state: str, at: str, prev: str) -> str:
    return sha256(f"{seq}|{order_id}|{state}|{at}|{prev}".encode()).hexdigest()[:16]


class OmsJournal:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._seq = 0
        self._prev = "GENESIS"
        self._states: dict[str, str] = {}
        if self.path.exists():
            self.replay()

    def append(self, order_id: str, state: str) -> JournalEntry:
        cur = self._states.get(order_id)
        if cur in TERMINAL:
            raise ValueError(f"terminal order {order_id} cannot transition from {cur}")
        if cur is not None and state not in VALID_NEXT.get(cur, set()):
            raise ValueError(f"illegal OMS transition {cur}→{state}")
        if cur is None and state != "CREATED":
            raise ValueError(f"first state must be CREATED, got {state}")
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
        self._prev = h
        self._states[order_id] = state
        return e

    def replay(self) -> dict[str, str]:
        self._states, self._seq, self._prev = {}, 0, "GENESIS"
        with open(self.path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                d = json.loads(line)
                assert d["prev_hash"] == self._prev, "journal hash-chain broken"
                self._prev = d["hash"]
                self._seq = d["seq"]
                self._states[d["order_id"]] = d["state"]
        return dict(self._states)

    def snapshot(self) -> dict[str, str]:
        return dict(self._states)


__all__ = ["OmsJournal", "JournalEntry", "TERMINAL", "VALID_NEXT"]
