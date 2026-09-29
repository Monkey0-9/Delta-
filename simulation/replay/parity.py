"""Replay parity harness (P1 slice, Group 16).

Proves microstructure replay is deterministic and venue-policy aware:
  - determinism: same event log replayed twice -> identical digest
  - ordering:   shuffled input is sorted by (ts_ns, seq) -> same digest
  - policy:     RETAIN_IF_DECREASE vs LOSE_PRIORITY produce the DOCUMENTED
                queue-position divergence on a decrease-replace
                (L2Engine.replace always resets priority — LOSE semantics;
                L3Book honors per-venue policy)
  - integrity:  no crossed book after replay (best bid < best ask)

Digests are sha256 over resting queue order + quantities + fill count,
so any nondeterminism fails loudly instead of drifting silently.
"""
from __future__ import annotations

import hashlib
from decimal import Decimal

from simulation.l3_engine import L3Book, L3Event, ReplacePriorityPolicy

METHOD = "l3-replay-parity-v1"


def replay(events: list[L3Event],
           policy: ReplacePriorityPolicy = ReplacePriorityPolicy.RETAIN_IF_DECREASE,
           ) -> tuple[L3Book, list]:
    ordered = sorted(events, key=lambda e: (e.ts_ns, e.seq))
    book = L3Book(policy=policy)
    fills: list = []
    for ev in ordered:
        fills.extend(book.apply(ev))
    return book, fills


def digest(book: L3Book, fills: list) -> str:
    parts: list[str] = []
    for side in ("bids", "asks"):
        levels = book._bids if side == "bids" else book._asks
        for px in sorted(levels):
            parts.append(f"{side}@{px}:" + ",".join(
                f"{r.order_id}x{r.qty}" for r in levels[px]))
    parts.append(f"fills={len(fills)}")
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:16]


def check_determinism(events: list[L3Event],
                      policy: ReplacePriorityPolicy = ReplacePriorityPolicy.RETAIN_IF_DECREASE,
                      ) -> dict:
    b1, f1 = replay(events, policy)
    b2, f2 = replay(events, policy)
    d1, d2 = digest(b1, f1), digest(b2, f2)
    return {"passed": d1 == d2, "digest": d1, "method": METHOD,
            "detail": f"two replays -> {d1} vs {d2}"}


def check_ordering(events: list[L3Event]) -> dict:
    """Out-of-order arrival must not change the book (sort by ts, seq)."""
    b1, f1 = replay(events)
    rev = list(reversed(events))
    b2, f2 = replay(rev)
    d1, d2 = digest(b1, f1), digest(b2, f2)
    return {"passed": d1 == d2, "digest": d1, "method": METHOD,
            "detail": f"ordered vs reversed input -> {d1} vs {d2}"}


def check_replace_policy_divergence() -> dict:
    """Decrease-replace keeps queue under RETAIN_IF_DECREASE, goes to back
    under LOSE_PRIORITY. Both outcomes asserted explicitly."""
    script = [
        L3Event(1, 1, "ADD", "a", "buy", Decimal("100"), Decimal("10")),
        L3Event(2, 2, "ADD", "b", "buy", Decimal("100"), Decimal("10")),
        L3Event(3, 3, "ADD", "c", "buy", Decimal("100"), Decimal("10")),
        L3Event(4, 4, "REPLACE", "b", "buy", Decimal("100"), Decimal("5")),
    ]
    br, _ = replay(script, ReplacePriorityPolicy.RETAIN_IF_DECREASE)
    bl, _ = replay(script, ReplacePriorityPolicy.LOSE_PRIORITY)
    pos_r, pos_l = br.queue_position("b"), bl.queue_position("b")
    passed = (pos_r == 1) and (pos_l == 2)
    return {"passed": passed, "method": METHOD,
            "retain_position": pos_r, "lose_position": pos_l,
            "detail": f"3-order decrease-replace: RETAIN pos={pos_r} (expect 1), "
                      f"LOSE pos={pos_l} (expect 2). L2Engine.replace documents "
                      f"LOSE semantics; L3Book honors per-venue policy."}


def check_no_crossed_book(book: L3Book) -> dict:
    top = book.top()
    bid, ask = top["bid"], top["ask"]
    ok = True if (bid is None or ask is None) else bool(bid < ask)
    return {"passed": ok, "method": METHOD, "bid": str(bid), "ask": str(ask),
            "detail": f"top bid={bid} ask={ask}"}


__all__ = ["METHOD", "check_determinism", "check_no_crossed_book",
           "check_ordering", "check_replace_policy_divergence",
           "digest", "replay"]
