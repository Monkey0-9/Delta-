"""Unified memory store: 6 kinds, versioned, hash-linked lineage.

Kinds: experience, failure, market_state, decision, research, model.
Same logical id -> version increments; each version links to the previous
fingerprint, so tampering or forking is detectable via verify().
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

KINDS = ("experience", "failure", "market_state", "decision", "research", "model")


@dataclass(frozen=True, slots=True)
class MemoryEntry:
    entry_id: str
    kind: str
    version: int
    payload: dict
    prev_fingerprint: str
    fingerprint: str

    def verify(self) -> bool:
        import hmac

        return hmac.compare_digest(self.fingerprint, _fingerprint(
            self.entry_id, self.kind, self.version, self.payload, self.prev_fingerprint))


def _fingerprint(entry_id: str, kind: str, version: int, payload: dict, prev: str) -> str:
    raw = json.dumps(
        {"id": entry_id, "kind": kind, "v": version, "payload": payload, "prev": prev},
        sort_keys=True, separators=(",", ":"), default=str,
    ).encode()
    return hashlib.sha256(raw).hexdigest()


class MemoryStore:
    def __init__(self) -> None:
        self._entries: dict[str, list[MemoryEntry]] = {}

    def append(self, entry_id: str, kind: str, payload: dict) -> MemoryEntry:
        if kind not in KINDS:
            raise ValueError(f"unknown kind: {kind}")
        if not entry_id.strip():
            raise ValueError("entry_id required.")
        chain = self._entries.get(entry_id, [])
        version = len(chain) + 1
        prev = chain[-1].fingerprint if chain else "0" * 64
        entry = MemoryEntry(entry_id, kind, version, dict(payload), prev,
                            _fingerprint(entry_id, kind, version, dict(payload), prev))
        chain.append(entry)
        self._entries[entry_id] = chain
        return entry

    def history(self, entry_id: str) -> tuple[MemoryEntry, ...]:
        return tuple(self._entries.get(entry_id, ()))

    def latest(self, entry_id: str) -> MemoryEntry | None:
        chain = self._entries.get(entry_id, [])
        return chain[-1] if chain else None

    def search(self, kind: str, predicate=None, limit: int = 50) -> list[MemoryEntry]:
        if kind not in KINDS:
            raise ValueError(f"unknown kind: {kind}")
        out = [chain[-1] for chain in self._entries.values() if chain and chain[-1].kind == kind]
        if predicate is not None:
            out = [e for e in out if predicate(e)]
        return out[: max(0, limit)]

    def verify_chain(self, entry_id: str) -> bool:
        chain = self._entries.get(entry_id, [])
        if not chain:
            return False
        prev = "0" * 64
        for i, entry in enumerate(chain, start=1):
            if entry.version != i or entry.prev_fingerprint != prev or not entry.verify():
                return False
            prev = entry.fingerprint
        return True
