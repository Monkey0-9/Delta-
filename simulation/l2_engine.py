"""W161-W170 deterministic L2/L3 event-driven matching engine.

Deterministic: seed -> identical books, queue positions, fills.
No global random; xorshift32 stream only. Every matching event carries
(seq, event_ns, type) so replay is bit-identical.

Covers: event clock, L1/L2/L3, price-time priority, queue position,
partial fills, cancel/replace lifecycle, hidden liquidity, matching events.
"""
from __future__ import annotations

import heapq
import itertools
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Literal

ENGINE_VERSION = "l2-engine-v1"
TICK = Decimal("0.01")

Side = Literal["buy", "sell"]
Action = Literal["ADD", "CANCEL", "REPLACE", "FILL", "HIDDEN_ADD", "REJECT"]


@dataclass(frozen=True, slots=True)
class MatchingEvent:
    seq: int
    event_ns: int
    type: str  # ADD | CANCEL | REPLACE | FILL | HIDDEN_ADD | REJECT | SWEEP
    order_id: str
    side: str
    price: Decimal
    quantity: Decimal
    queue_position: int = -1  # -1 = not queued (marketable/hidden)
    hidden: bool = False


@dataclass(frozen=True, slots=True)
class EngineFill:
    seq: int
    event_ns: int
    buy_id: str
    sell_id: str
    price: Decimal
    quantity: Decimal
    maker_id: str  # resting order (maker)
    taker_id: str  # incoming order (taker)


@dataclass
class _Resting:
    order_id: str
    side: Side
    price: Decimal
    quantity: Decimal
    hidden: bool
    seq: int


@dataclass
class L2Engine:
    """Deterministic price-time-priority book with L3 order lifecycle."""

    seed: int = 7
    _bids: dict = field(default_factory=dict)  # price -> list[_Resting] FIFO
    _asks: dict = field(default_factory=dict)
    _index: dict = field(default_factory=dict)  # order_id -> (price, side)
    _pending: list = field(default_factory=list)  # heap (arrival_ns, seq, payload)
    _events: list = field(default_factory=list)  # list[MatchingEvent]
    _fills: list = field(default_factory=list)  # list[EngineFill]
    _seq: int = 0
    _ns: int = 0
    _rng: int = 0

    def __post_init__(self) -> None:
        self._rng = self.seed & 0xFFFFFFFF or 1
        self._counter = itertools.count()

    # -- deterministic RNG --
    def _rand(self) -> float:
        x = self._rng
        x ^= (x << 13) & 0xFFFFFFFF
        x ^= x >> 17
        x ^= (x << 5) & 0xFFFFFFFF
        self._rng = x
        return x / 0xFFFFFFFF

    def _emit(self, type: str, order_id: str, side: str, price: Decimal,
              quantity: Decimal, queue_position: int = -1, hidden: bool = False) -> None:
        self._seq += 1
        self._events.append(MatchingEvent(
            seq=self._seq, event_ns=self._ns, type=type, order_id=order_id,
            side=side, price=price, quantity=quantity,
            queue_position=queue_position, hidden=hidden))

    # -- L3 lifecycle --
    def add(self, order_id: str, side: Side, price: Decimal, quantity: Decimal,
            hidden: bool = False, latency_ns: int = 0) -> int:
        """Stage an order; it crosses when the event clock reaches arrival_ns."""
        if quantity <= 0 or price <= 0:
            self._emit("REJECT", order_id, side, price, quantity)
            raise ValueError("quantity and price must be positive.")
        if order_id in self._index:
            self._emit("REJECT", order_id, side, price, quantity)
            raise ValueError(f"duplicate order_id: {order_id}.")
        jitter = int(self._rand() * 20_000)  # 0-20us deterministic
        arrival = self._ns + latency_ns + jitter
        heapq.heappush(self._pending, (arrival, next(self._counter),
                                       (order_id, side, price, quantity, hidden)))
        return arrival

    def cancel(self, order_id: str) -> bool:
        loc = self._index.get(order_id)
        # also drop not-yet-arrived staged orders
        before = len(self._pending)
        self._pending = [e for e in self._pending if e[2][0] != order_id]
        if len(self._pending) != before:
            heapq.heapify(self._pending)
            self._emit("CANCEL", order_id, "", Decimal("0"), Decimal("0"))
            return True
        if loc is None:
            return False
        price, side = loc
        book = self._bids if side == "buy" else self._asks
        level = book.get(price, [])
        book[price] = [r for r in level if r.order_id != order_id]
        if not book[price]:
            book.pop(price, None)
        self._index.pop(order_id, None)
        self._emit("CANCEL", order_id, side, price, Decimal("0"))
        return True

    def replace(self, order_id: str, new_price: Decimal, new_quantity: Decimal) -> bool:
        """Cancel/replace: price-time priority resets (new queue position)."""
        loc = self._index.get(order_id)
        if loc is None or new_price <= 0 or new_quantity <= 0:
            return False
        _, side = loc
        hidden = next((r.hidden for lvl in (self._bids if side == "buy" else self._asks).values()
                       for r in lvl if r.order_id == order_id), False)
        self.cancel(order_id)
        self._cross_now(order_id, side, new_price, new_quantity, hidden)
        self._emit("REPLACE", order_id, side, new_price, new_quantity, hidden=hidden)
        return True

    def queue_position(self, order_id: str) -> int:
        loc = self._index.get(order_id)
        if loc is None:
            return -1
        price, side = loc
        level = (self._bids if side == "buy" else self._asks).get(price, [])
        for i, r in enumerate(level):
            if r.order_id == order_id:
                return i
        return -1

    # -- event clock --
    def step_until(self, target_ns: int) -> list[EngineFill]:
        out: list[EngineFill] = []
        n0 = len(self._fills)
        while self._pending and self._pending[0][0] <= target_ns:
            arrival, _, (oid, side, price, qty, hidden) = heapq.heappop(self._pending)
            self._ns = max(self._ns, arrival)
            self._cross_now(oid, side, price, qty, hidden)
        self._ns = max(self._ns, target_ns)
        out.extend(self._fills[n0:])
        return out

    def _cross_now(self, order_id: str, side: Side, price: Decimal,
                   quantity: Decimal, hidden: bool) -> None:
        remaining = quantity
        if side == "buy":
            while remaining > 0 and self._asks:
                best = min(self._asks)
                if best > price:
                    break
                level = self._asks[best]
                # visible first, hidden last at same price
                level.sort(key=lambda r: (r.hidden, r.seq))
                resting = level[0]
                fill_qty = min(remaining, resting.quantity)
                self._record_fill(resting.order_id, order_id, best, fill_qty,
                                  maker_id=resting.order_id, taker_id=order_id)
                resting.quantity -= fill_qty
                remaining -= fill_qty
                if resting.quantity <= 0:
                    level.pop(0)
                    self._index.pop(resting.order_id, None)
                if not level:
                    self._asks.pop(best, None)
        else:
            while remaining > 0 and self._bids:
                best = max(self._bids)
                if best < price:
                    break
                level = self._bids[best]
                level.sort(key=lambda r: (r.hidden, r.seq))
                resting = level[0]
                fill_qty = min(remaining, resting.quantity)
                self._record_fill(order_id, resting.order_id, best, fill_qty,
                                  maker_id=resting.order_id, taker_id=order_id)
                resting.quantity -= fill_qty
                remaining -= fill_qty
                if resting.quantity <= 0:
                    level.pop(0)
                    self._index.pop(resting.order_id, None)
                if not level:
                    self._bids.pop(best, None)
        if remaining > 0:
            self._seq += 1
            book = self._bids if side == "buy" else self._asks
            level = book.setdefault(price, [])
            qp = len(level)
            level.append(_Resting(order_id, side, price, remaining, hidden, self._seq))
            self._index[order_id] = (price, side)
            self._emit("HIDDEN_ADD" if hidden else "ADD", order_id, side,
                       price, remaining, queue_position=qp, hidden=hidden)

    def _record_fill(self, buy_id: str, sell_id: str, price: Decimal,
                     quantity: Decimal, maker_id: str, taker_id: str) -> None:
        self._seq += 1
        self._fills.append(EngineFill(seq=self._seq, event_ns=self._ns, buy_id=buy_id,
                                      sell_id=sell_id, price=price, quantity=quantity,
                                      maker_id=maker_id, taker_id=taker_id))
        self._events.append(MatchingEvent(seq=self._seq, event_ns=self._ns, type="FILL",
                                          order_id=taker_id, side="", price=price,
                                          quantity=quantity))

    # -- L1/L2 views --
    def best_bid(self) -> Decimal | None:
        return max(self._bids) if self._bids else None

    def best_ask(self) -> Decimal | None:
        return min(self._asks) if self._asks else None

    def l2_snapshot(self, depth: int = 10) -> dict:
        bids = sorted(self._bids, reverse=True)[:depth]
        asks = sorted(self._asks)[:depth]
        return {
            "bids": [(p, sum(r.quantity for r in self._bids[p] if not r.hidden)) for p in bids],
            "asks": [(p, sum(r.quantity for r in self._asks[p] if not r.hidden)) for p in asks],
            "seq": self._seq, "ns": self._ns, "engine": ENGINE_VERSION,
        }

    @property
    def fills(self) -> list[EngineFill]:
        return list(self._fills)

    @property
    def events(self) -> list[MatchingEvent]:
        return list(self._events)

    @property
    def pending(self) -> int:
        return len(self._pending)
