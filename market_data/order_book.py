from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from core.domain.timestamp import ensure_utc, utc_now


@dataclass(frozen=True, slots=True)
class BookLevel:
    price: Decimal
    quantity: Decimal


@dataclass(frozen=True, slots=True)
class OrderBook:
    instrument_id: UUID
    bids: tuple[BookLevel, ...] = ()
    asks: tuple[BookLevel, ...] = ()
    event_time: datetime = field(default_factory=utc_now)
    received_time: datetime = field(default_factory=utc_now)
    source: str = "unknown"
    schema_version: int = 1
    event_id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        object.__setattr__(self, "event_time", ensure_utc(self.event_time))
        object.__setattr__(self, "received_time", ensure_utc(self.received_time))
        bids = sorted(self.bids, key=lambda l: l.price, reverse=True)
        asks = sorted(self.asks, key=lambda l: l.price)
        object.__setattr__(self, "bids", tuple(bids))
        object.__setattr__(self, "asks", tuple(asks))
        if bids and asks and asks[0].price < bids[0].price:
            raise ValueError("crossed book: best ask below best bid.")

    @property
    def best_bid(self) -> BookLevel | None:
        return self.bids[0] if self.bids else None

    @property
    def best_ask(self) -> BookLevel | None:
        return self.asks[0] if self.asks else None

    @property
    def spread(self) -> Decimal | None:
        if self.bids and self.asks:
            return self.asks[0].price - self.bids[0].price
        return None

    @property
    def mid(self) -> Decimal | None:
        if self.bids and self.asks:
            return (self.asks[0].price + self.bids[0].price) / Decimal("2")
        return None

    def depth(self, levels: int = 5) -> tuple[Decimal, Decimal]:
        """Aggregate (bid_qty, ask_qty) over top-N levels."""
        b = sum((l.quantity for l in self.bids[:levels]), Decimal("0"))
        a = sum((l.quantity for l in self.asks[:levels]), Decimal("0"))
        return b, a

    def imbalance(self, levels: int = 5) -> Decimal | None:
        """(bid-ask)/(bid+ask) in [-1, 1]; None when book empty."""
        b, a = self.depth(levels)
        tot = b + a
        if tot <= 0:
            return None
        return (b - a) / tot

    def microprice(self, levels: int = 1) -> Decimal | None:
        """Volume-weighted microprice from top-N levels."""
        b, a = self.depth(levels)
        tot = b + a
        if tot <= 0 or not self.bids or not self.asks:
            return None
        return (
            self.asks[0].price * b + self.bids[0].price * a
        ) / tot

    def apply_delta(
        self, *, bids: tuple[BookLevel, ...] = (), asks: tuple[BookLevel, ...] = ()
    ) -> OrderBook:
        """Return a new book with zero-quantity levels removed, others upserted.

        Keeps immutability + crossed-book invariant via __post_init__.
        """
        def _merge(cur: tuple[BookLevel, ...], upd: tuple[BookLevel, ...]) -> tuple[BookLevel, ...]:
            book: dict[Decimal, Decimal] = {l.price: l.quantity for l in cur}
            for l in upd:
                if l.quantity <= 0:
                    book.pop(l.price, None)
                else:
                    book[l.price] = l.quantity
            return tuple(BookLevel(p, q) for p, q in book.items())

        return OrderBook(
            instrument_id=self.instrument_id,
            bids=_merge(self.bids, bids),
            asks=_merge(self.asks, asks),
            event_time=self.event_time,
            received_time=self.received_time,
            source=self.source,
        )
