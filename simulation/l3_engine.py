"""P2 — Institutional Microstructure Engine (W127/W128/W129).

L3 order events -> exchange matching rules -> queue position ->
latency -> partial fills -> cancel/replace -> adverse selection ->
market impact -> execution result. Calibrated against executions.

Deterministic: integer ns clock, seeded xorshift, no wall clock.
W127: L3 order-book engine. W128: exchange matching simulator.
W129: latency + queue calibration.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

ENGINE_VERSION = "microstructure-v1"


@dataclass(frozen=True, slots=True)
class L3Event:
    seq: int
    ts_ns: int
    kind: str  # ADD|CANCEL|REPLACE|MARKET|FILL|EXPIRE
    order_id: str
    side: str  # buy|sell
    price: Decimal
    qty: Decimal


@dataclass(frozen=True, slots=True)
class Fill:
    seq: int
    ts_ns: int
    taker_id: str
    maker_id: str
    price: Decimal
    qty: Decimal
    maker_queue_pos: int


@dataclass
class _Rest:
    order_id: str
    side: str
    price: Decimal
    qty: Decimal
    ts_ns: int
    seq: int


@dataclass
class L3Book:
    """Price-time priority L3 book with queue positions and cancel/replace."""

    _bids: dict = field(default_factory=dict)
    _asks: dict = field(default_factory=dict)
    _idx: dict = field(default_factory=dict)  # id -> (price, side)
    _fills: list = field(default_factory=list)
    _seq: int = 0

    def queue_position(self, order_id: str) -> int:
        loc = self._idx.get(order_id)
        if not loc:
            return -1
        price, side = loc
        q = self._bids.get(price, []) if side == "buy" else self._asks.get(price, [])
        for i, r in enumerate(q):
            if r.order_id == order_id:
                return i
        return -1

    def queue_ahead_qty(self, order_id: str) -> Decimal:
        loc = self._idx.get(order_id)
        if not loc:
            return Decimal(0)
        price, side = loc
        q = self._bids.get(price, []) if side == "buy" else self._asks.get(price, [])
        tot = Decimal(0)
        for r in q:
            if r.order_id == order_id:
                break
            tot += r.qty
        return tot

    def apply(self, ev: L3Event) -> list[Fill]:
        self._seq = max(self._seq + 1, ev.seq)
        if ev.kind == "ADD":
            return self._add(ev)
        if ev.kind == "MARKET":
            return self._market(ev)
        if ev.kind == "CANCEL":
            self._cancel(ev.order_id)
            return []
        if ev.kind == "REPLACE":
            self._cancel(ev.order_id)
            return self._add(ev)
        if ev.kind == "EXPIRE":
            self._cancel(ev.order_id)
            return []
        return []

    def _book(self, side: str) -> dict:
        return self._bids if side == "buy" else self._asks

    def _add(self, ev: L3Event) -> list[Fill]:
        # marketable limit crosses immediately
        fills = self._match(ev.side, ev.price, ev.qty, ev.order_id, ev.ts_ns, limit=True)
        filled = sum((f.qty for f in fills), Decimal(0))
        rest = ev.qty - filled
        if rest > 0:
            r = _Rest(ev.order_id, ev.side, ev.price, rest, ev.ts_ns, ev.seq)
            self._book(ev.side).setdefault(ev.price, []).append(r)
            self._idx[ev.order_id] = (ev.price, ev.side)
        return fills

    def _market(self, ev: L3Event) -> list[Fill]:
        px = Decimal("-1") if ev.side == "buy" else Decimal("10e12")
        return self._match(ev.side, px, ev.qty, ev.order_id, ev.ts_ns, limit=False)

    def _cancel(self, oid: str) -> bool:
        loc = self._idx.pop(oid, None)
        if not loc:
            return False
        price, side = loc
        q = self._book(side).get(price, [])
        self._book(side)[price] = [r for r in q if r.order_id != oid]
        return True

    def _match(self, side: str, price: Decimal, qty: Decimal, taker: str, ts_ns: int, *, limit: bool) -> list[Fill]:
        out: list[Fill] = []
        opp = self._asks if side == "buy" else self._bids
        remain = qty
        while remain > 0 and opp:
            best = min(opp) if side == "buy" else max(opp)
            if limit and ((side == "buy" and best > price) or (side == "sell" and best < price)):
                break
            q = opp[best]
            # snapshot queue positions before consuming
            while remain > 0 and q:
                maker = q[0]
                pos = 0  # head of queue always executes first
                take = min(remain, maker.qty)
                self._seq += 1
                out.append(Fill(self._seq, ts_ns, taker, maker.order_id, best, take, pos))
                self._fills.append(out[-1])
                remain -= take
                maker.qty -= take
                if maker.qty <= 0:
                    q.pop(0)
                    self._idx.pop(maker.order_id, None)
            if not q:
                opp.pop(best, None)
        return out

    @property
    def fills(self) -> list[Fill]:
        return list(self._fills)

    def top(self) -> dict:
        bid = max(self._bids) if self._bids else None
        ask = min(self._asks) if self._asks else None
        return {"bid": bid, "ask": ask}


@dataclass(frozen=True, slots=True)
class LatencyModel:
    """Deterministic latency: fixed + jitter(seed, seq). W129."""

    base_ns: int = 50_000
    jitter_ns: int = 10_000
    seed: int = 7

    def one_way_ns(self, seq: int) -> int:
        x = (self.seed ^ (seq * 0x9E3779B1)) & 0xFFFFFFFF or 1
        x ^= (x << 13) & 0xFFFFFFFF
        x ^= x >> 17
        x ^= (x << 5) & 0xFFFFFFFF
        return self.base_ns + int(x % (self.jitter_ns + 1))

    def arrival_ns(self, send_ns: int, seq: int) -> int:
        return send_ns + self.one_way_ns(seq)


@dataclass
class QueueCalibrator:
    """W129: estimate queue-depletion / adverse-selection from fills."""

    def depletion_ratio(self, book: L3Book, order_id: str, initial_ahead: Decimal) -> float:
        if initial_ahead <= 0:
            return 1.0
        ahead = book.queue_ahead_qty(order_id)
        return float(max(Decimal(0), initial_ahead - ahead) / initial_ahead)

    def adverse_selection_bps(self, fill_px: float, post_mid: float, side: str) -> float:
        # buy filled then mid drops => adverse; sell filled then mid rises => adverse
        if side == "buy":
            return (fill_px - post_mid) / fill_px * 1e4
        return (post_mid - fill_px) / fill_px * 1e4


@dataclass(frozen=True, slots=True)
class ImpactEstimate:
    temporary_bps: float
    permanent_bps: float
    total_bps: float


class SquareRootImpact:
    """Empirical square-root impact: I = sigma * gamma * sqrt(Q/ADV)."""

    def __init__(self, gamma: float = 0.5, permanent_share: float = 0.4) -> None:
        self.gamma = gamma
        self.perm = permanent_share

    def estimate(self, qty: float, adv: float, sigma: float) -> ImpactEstimate:
        if adv <= 0 or qty <= 0:
            return ImpactEstimate(0.0, 0.0, 0.0)
        tot = float(sigma) * self.gamma * (float(qty) / float(adv)) ** 0.5 * 1e4
        return ImpactEstimate(tot * (1 - self.perm), tot * self.perm, tot)


def calibrate_gamma(executions: list[tuple[float, float, float, float]]) -> float:
    """Calibrate gamma from (qty, adv, sigma, realized_bps) via least squares.

    executions: list of (qty, adv, sigma_frac, realized_total_bps).
    Returns gamma minimizing squared error under sqrt model.
    """
    num = den = 0.0
    for qty, adv, sigma,bps in executions:
        if adv <= 0 or qty <= 0 or sigma <= 0:
            continue
        x = sigma * (qty / adv) ** 0.5 * 1e4
        num += x * bps
        den += x * x
    if den <= 0:
        return 0.5
    g = num / den
    return max(0.01, min(5.0, g))
