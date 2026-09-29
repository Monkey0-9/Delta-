"""L2 order-book replay from historical update streams.

Uses research.microstructure.OrderBook when importable; otherwise falls
back to a lightweight dict-based book. Handles timestamp alignment and
out-of-order updates via (timestamp, sequence) sorting. Pandas/numpy only.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterator

import numpy as np
import pandas as pd

try:
    from research.microstructure.order_book import (
        Order,
        OrderBook,
        OrderType,
        Side,
    )

    _HAS_OB = True
except Exception:  # offline-safe fallback
    Order = OrderBook = OrderType = Side = None  # type: ignore[assignment]
    _HAS_OB = False

__all__ = ["L2Replay", "L2Update", "ReplayState"]


@dataclass(frozen=True, slots=True)
class L2Update:
    """Normalized single book update."""

    timestamp: float
    seq: int
    side: str
    price: float
    quantity: float
    action: str = "add"
    order_id: str = ""


@dataclass(frozen=True, slots=True)
class ReplayState:
    """Book state yielded after applying one update."""

    timestamp: float
    bids: tuple = field(default_factory=tuple)
    asks: tuple = field(default_factory=tuple)
    best_bid: float | None = None
    best_ask: float | None = None
    spread: float | None = None
    mid: float | None = None


def _to_float_ts(value: Any) -> float:
    if value is None:
        raise ValueError("update is missing a timestamp")
    if isinstance(value, (int, float, np.floating)):
        return float(value)
    return float(pd.Timestamp(value).timestamp())


class L2Replay:
    """Load, sort and replay L2 book updates."""

    def __init__(self, symbol: str = "SYM", depth: int = 10) -> None:
        self._symbol = symbol
        self._depth = depth
        self._updates: list[L2Update] = []

    @property
    def symbol(self) -> str:
        return self._symbol

    def load_updates(self, updates: list[dict]) -> "L2Replay":
        """Normalize, timestamp-align and time-sort raw update dicts.

        Accepted keys per dict: timestamp/ts/time, side, price,
        quantity/qty/size, action (add/remove/modify), order_id.
        Out-of-order rows are sorted by (timestamp, sequence).
        """
        norm: list[L2Update] = []
        for i, raw in enumerate(updates):
            ts_raw = raw.get("timestamp", raw.get("ts", raw.get("time")))
            side = str(raw.get("side", "BUY")).upper()
            if side in ("B", "BID"):
                side = "BUY"
            elif side in ("S", "ASK"):
                side = "SELL"
            if side not in ("BUY", "SELL"):
                raise ValueError(f"bad side: {raw.get('side')!r}")
            action = str(raw.get("action", "add")).lower()
            if action not in ("add", "remove", "modify", "cancel"):
                raise ValueError(f"bad action: {action!r}")
            qty = raw.get("quantity", raw.get("qty", raw.get("size", 0.0)))
            norm.append(
                L2Update(
                    timestamp=_to_float_ts(ts_raw),
                    seq=i,
                    side=side,
                    price=float(raw.get("price", 0.0)),
                    quantity=float(qty),
                    action="remove" if action == "cancel" else action,
                    order_id=str(raw.get("order_id", f"upd_{i}")),
                )
            )
        norm.sort(key=lambda u: (u.timestamp, u.seq))
        self._updates = norm
        return self

    # -- book backends -------------------------------------------------
    def _new_book(self) -> Any:
        if _HAS_OB:
            return OrderBook(symbol=self._symbol)
        return {"bids": {}, "asks": {}}

    def _apply(self, book: Any, upd: L2Update) -> None:
        if _HAS_OB:
            self._apply_ob(book, upd)
        else:
            self._apply_dict(book, upd)

    def _apply_ob(self, book: Any, upd: L2Update) -> None:
        if upd.action == "remove":
            book.remove_order(upd.order_id)
            return
        if upd.action == "modify":
            if not book.modify_order(upd.order_id, upd.quantity):
                book.add_order(self._mk_order(upd))
            return
        if upd.order_id in book.orders:
            book.remove_order(upd.order_id)
        if upd.quantity > 0:
            book.add_order(self._mk_order(upd))

    def _mk_order(self, upd: L2Update) -> Any:
        return Order(
            order_id=upd.order_id,
            symbol=self._symbol,
            side=Side.BUY if upd.side == "BUY" else Side.SELL,
            order_type=OrderType.LIMIT,
            price=upd.price,
            quantity=upd.quantity,
            timestamp=upd.timestamp,
        )

    @staticmethod
    def _apply_dict(book: dict, upd: L2Update) -> None:
        side_map = book["bids"] if upd.side == "BUY" else book["asks"]
        if upd.action == "remove" or upd.quantity <= 0:
            side_map.pop(upd.price, None)
        else:
            side_map[upd.price] = upd.quantity

    def _state(self, book: Any, ts: float) -> ReplayState:
        if _HAS_OB:
            bids, asks = book.get_depth(self._depth)
            bid_lv = tuple((lv.price, lv.total_quantity) for lv in bids)
            ask_lv = tuple((lv.price, lv.total_quantity) for lv in asks)
            return ReplayState(
                timestamp=ts,
                bids=bid_lv,
                asks=ask_lv,
                best_bid=book.get_best_bid(),
                best_ask=book.get_best_ask(),
                spread=book.get_spread(),
                mid=book.get_mid_price(),
            )
        bids = dict(sorted(book["bids"].items(), reverse=True)[: self._depth])
        asks = dict(sorted(book["asks"].items())[: self._depth])
        bid_lv = tuple(bids.items())
        ask_lv = tuple(asks.items())
        bb = bid_lv[0][0] if bid_lv else None
        ba = ask_lv[0][0] if ask_lv else None
        spread = (ba - bb) if bb is not None and ba is not None else None
        mid = ((ba + bb) / 2.0) if bb is not None and ba is not None else None
        return ReplayState(
            timestamp=ts, bids=bid_lv, asks=ask_lv,
            best_bid=bb, best_ask=ba, spread=spread, mid=mid,
        )

    # -- public API ----------------------------------------------------
    def reconstruct_book(self) -> ReplayState:
        """Apply all loaded updates; return the final book state."""
        book = self._new_book()
        last_ts = 0.0
        for upd in self._updates:
            self._apply(book, upd)
            last_ts = upd.timestamp
        return self._state(book, last_ts)

    def replay(self) -> Iterator[ReplayState]:
        """Yield the book state after each update, in time order."""
        book = self._new_book()
        for upd in self._updates:
            self._apply(book, upd)
            yield self._state(book, upd.timestamp)
