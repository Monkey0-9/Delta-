"""W142/W143/W144 — Distributed replay, multi-venue SOR, FIX/exchange certification.

Deterministic venue-router (Smart Order Router) with venue fee/liquidity
profiles; FIX session stub with sequence-number certification; sharded
replay coordinator producing identical results regardless of shard count.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class Venue:
    venue_id: str
    fee_bps: float
    latency_ns: int
    depth: float  # available size proxy


@dataclass(frozen=True, slots=True)
class ChildOrder:
    venue_id: str
    qty: float
    px_limit: float


class SmartOrderRouter:
    """Liquidity-aware split: prefer low fee*latency-adjusted cost with depth cap."""

    def route(self, qty: float, px: float, venues: list[Venue]) -> list[ChildOrder]:
        if qty <= 0 or not venues:
            return []
        # score = fee + latency penalty; allocate pro-rata to depth/score
        weights = []
        for v in venues:
            score = v.fee_bps + v.latency_ns / 1e6
            weights.append((v.depth / max(score, 1e-9), v))
        tot = sum(w for w, _ in weights) or 1.0
        out, rem = [], qty
        for i, (w, v) in enumerate(weights):
            alloc = round(qty * w / tot, 6) if i < len(weights) - 1 else round(rem, 6)
            alloc = min(alloc, v.depth, rem)
            if alloc > 0:
                out.append(ChildOrder(v.venue_id, alloc, px))
                rem = round(rem - alloc, 6)
        return out


@dataclass
class FixSession:
    """FIX 4.4 session stub: monotonic seq nums, gap detection, cert checklist."""

    target: str = "EXCH"
    out_seq: int = 1
    in_seq: int = 1
    gaps: int = 0

    def send(self) -> int:
        s = self.out_seq
        self.out_seq += 1
        return s

    def receive(self, seq: int) -> bool:
        if seq == self.in_seq:
            self.in_seq += 1
            return True
        if seq > self.in_seq:
            self.gaps += 1
            self.in_seq = seq + 1
            return False
        return True  # duplicate -> idempotent

    def certify(self) -> dict:
        return {"target": self.target, "out_seq": self.out_seq,
                "gaps_seen": self.gaps, "certified": self.gaps == 0 and self.out_seq > 1}


def sharded_replay(events: list[int], n_shards: int) -> list[int]:
    """Deterministic sharded map (sort+process) invariant to shard count."""
    shards: list[list[int]] = [[] for _ in range(max(n_shards, 1))]
    for i, e in enumerate(events):
        shards[i % len(shards)].append(e)
    # each shard sorts locally then global k-way merge == full sort
    for s in shards:
        s.sort()
    out = sorted(e for s in shards for e in s)
    return out
