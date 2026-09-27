"""Paper FIX venue: deterministic execution simulator behind FIX framing.

Accepts NewOrderSingle(D) -> immediate ExecutionReport(8) full fill at the
reference price (mid +/- half-spread cross), plus Cancel(F) -> URouted/4
cancel report for resting PAPER orders. Sequence discipline enforced via
FixSession on both sides in tests. Fees in tag 12. Deterministic per seed.

This is a TEST venue, not a market: fills never depend on real liquidity and
every report is labeled venue=DELTA-PAPER.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from execution.fix import codec as C
from execution.fix.session import FixSession

VENUE = "DELTA-PAPER"


@dataclass
class PaperFixVenue:
    seed: int = 7
    half_spread_bps: float = 2.5
    fee_bps: float = 1.0
    session: FixSession = field(default_factory=lambda: FixSession(VENUE, "DELTA"))
    resting: dict = field(default_factory=dict)  # clOrdID -> order dict
    seen: set = field(default_factory=set)  # every accepted ClOrdID, ever
    _exec_n: int = 0

    def _px(self, ref: float, side: str) -> float:
        adj = ref * self.half_spread_bps / 1e4
        return ref + adj if side == "1" else ref - adj

    def on_message(self, raw: str, ref_price: float, transact_time: str) -> list[str]:
        """Process one inbound FIX string; returns outbound FIX strings."""
        msg = self.session.receive(raw)
        if "__gap__" in msg:
            return [msg["__resend__"]]
        mt = msg.get("35")
        if mt == "A":
            return [self.session.send([("35", "A"), ("98", "0"), ("108", "30")])]
        if mt == "0":
            return []
        if mt == "D":
            C.require(msg, "D")
            oid = msg["11"]
            if oid in self.seen:
                rej = self.session.send([("35", "j"), ("45", msg.get("34", "0")),
                                         ("58", f"duplicate ClOrdID {oid}")])
                return [rej]
            self.seen.add(oid)
            qty = int(msg["38"])
            side = msg["54"]
            px = self._px(ref_price, side)
            self._exec_n += 1
            exec_id = f"EX-{self.seed}-{self._exec_n}"
            fee = qty * px * self.fee_bps / 1e4
            rep = self.session.send([("35", "8"), ("11", oid), ("17", exec_id),
                                     ("150", "2"), ("39", "2"), ("55", msg["55"]),
                                     ("54", side), ("38", str(qty)),
                                     ("32", str(qty)), ("31", f"{px:.4f}"),
                                     ("12", f"{fee:.4f}"), ("60", transact_time),
                                     ("122", VENUE)])
            return [rep]
        if mt == "F":
            C.require(msg, "F")
            orig = msg["41"]
            ok = self.resting.pop(orig, None) is not None
            rep = self.session.send([("35", "8"), ("11", msg["11"]), ("41", orig),
                                     ("17", f"CX-{self.seed}-{self._exec_n}"),
                                     ("150", "4" if ok else "8"),
                                     ("39", "4" if ok else "8"),
                                     ("58", "cancelled" if ok else "unknown order"),
                                     ("60", transact_time)])
            return [rep]
        if mt == "5":
            return [self.session.send([("35", "5")])]
        rej = self.session.send([("35", "3"), ("45", msg.get("34", "0")),
                                 ("58", f"unsupported {mt}")])
        return [rej]

    def rest(self, cl_ord_id: str, order: dict) -> None:
        """Rest a paper order (cancelable later). Deterministic id from content."""
        if cl_ord_id in self.resting:
            raise C.FixReject(f"duplicate ClOrdID {cl_ord_id}.", business=True)
        order = dict(order)
        order["tag122"] = VENUE
        order["digest"] = hashlib.sha256(repr(sorted(order.items())).encode()
                                         ).hexdigest()[:12]
        self.resting[cl_ord_id] = order


__all__ = ["VENUE", "PaperFixVenue"]
