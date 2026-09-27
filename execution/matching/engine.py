"""Price-time priority matching engine (reference Python implementation)."""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from decimal import Decimal


@dataclass
class RestingOrder:
    order_id: str
    side: str  # "buy" | "sell"
    price: Decimal
    quantity: Decimal
    sequence: int


@dataclass(frozen=True, slots=True)
class MatchFill:
    buy_id: str
    sell_id: str
    price: Decimal
    quantity: Decimal


class PriceTimeMatcher:
    """FIFO within price level. Buy levels descending, sell ascending."""

    def __init__(self) -> None:
        self._bids: dict[Decimal, deque[RestingOrder]] = {}
        self._asks: dict[Decimal, deque[RestingOrder]] = {}
        self._seq = 0

    def add(self, order_id: str, side: str, price: Decimal, quantity: Decimal) -> list[MatchFill]:
        if side not in ("buy", "sell"):
            raise ValueError("side must be buy|sell.")
        if price <= 0 or quantity <= 0:
            raise ValueError("price/quantity must be positive.")
        self._seq += 1
        incoming = RestingOrder(order_id, side, price, quantity, self._seq)
        return self._match(incoming)

    def _match(self, incoming: RestingOrder) -> list[MatchFill]:
        fills: list[MatchFill] = []
        if incoming.side == "buy":
            while incoming.quantity > 0:
                best = self._best_ask_for(incoming.price)
                if best is None:
                    self._rest(self._bids, incoming)
                    break
                resting = best[0]
                q = min(incoming.quantity, resting.quantity)
                fills.append(MatchFill(incoming.order_id, resting.order_id, resting.price, q))
                incoming.quantity -= q
                resting.quantity -= q
                if resting.quantity <= 0:
                    best.popleft()
        else:
            while incoming.quantity > 0:
                best = self._best_bid_for(incoming.price)
                if best is None:
                    self._rest(self._asks, incoming)
                    break
                resting = best[0]
                q = min(incoming.quantity, resting.quantity)
                fills.append(MatchFill(resting.order_id, incoming.order_id, resting.price, q))
                incoming.quantity -= q
                resting.quantity -= q
                if resting.quantity <= 0:
                    best.popleft()
        return fills

    def _best_ask_for(self, price: Decimal) -> deque[RestingOrder] | None:
        cands = [p for p in self._asks if p <= price and self._asks[p]]
        if not cands:
            return None
        return self._asks[min(cands)]

    def _best_bid_for(self, price: Decimal) -> deque[RestingOrder] | None:
        cands = [p for p in self._bids if p >= price and self._bids[p]]
        if not cands:
            return None
        return self._bids[max(cands)]

    @staticmethod
    def _rest(book: dict[Decimal, deque[RestingOrder]], o: RestingOrder) -> None:
        book.setdefault(o.price, deque()).append(o)
