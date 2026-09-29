"""Smart order router (DELTA OS).

Splits a parent order across venues pro-rata to inverse cost weighted by
liquidity. Stdlib only; Decimal-optional inputs.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, List, Mapping, Optional, Tuple, Union

from .venue_models import VENUES, Venue, venue_cost

__all__ = ["SmartOrderRouter", "OrderRequest"]

Number = Union[int, float, Decimal]


@dataclass(frozen=True, slots=True)
class OrderRequest:
    """Minimal parent-order view accepted by the router."""

    symbol: str
    qty: float
    price: float
    side: str = "buy"


def _to_float(x: Number) -> float:
    return float(x)


def _parse_order(order: Union[Mapping, OrderRequest, Tuple, List]) -> OrderRequest:
    if isinstance(order, OrderRequest):
        return order
    if isinstance(order, Mapping):
        symbol = str(order.get("symbol", "UNKNOWN"))
        qty = order.get("qty", order.get("quantity", order.get("size", 0)))
        price = order.get("price", order.get("px", order.get("limit", 0)))
        side = str(order.get("side", "buy"))
        return OrderRequest(symbol=symbol, qty=_to_float(qty), price=_to_float(price), side=side)
    if isinstance(order, (tuple, list)) and len(order) >= 2:
        qty, price = order[0], order[1]
        symbol = str(order[2]) if len(order) > 2 else "UNKNOWN"
        return OrderRequest(symbol=symbol, qty=_to_float(qty), price=_to_float(price))
    if hasattr(order, "qty") and hasattr(order, "price"):
        return OrderRequest(
            symbol=str(getattr(order, "symbol", "UNKNOWN")),
            qty=_to_float(order.qty),  # type: ignore[attr-defined]
            price=_to_float(order.price),  # type: ignore[attr-defined]
            side=str(getattr(order, "side", "buy")),
        )
    raise TypeError(f"unsupported order type: {type(order)!r}")


class SmartOrderRouter:
    """Liquidity-aware router over a venue set.

    Score (lower is better) = venue_cost / liquidity_score, so cheap deep
    venues win. Routing allocates pro-rata to (liquidity / cost).
    """

    def __init__(self, venues: Optional[Union[Mapping[str, Venue], List[Venue], Dict[str, Venue]]] = None):
        if venues is None:
            self._venues: Dict[str, Venue] = dict(VENUES)
        elif isinstance(venues, Mapping):
            self._venues = dict(venues)
        else:
            self._venues = {v.id: v for v in venues}
        if not self._venues:
            raise ValueError("at least one venue is required.")
        self._last_qty: float = 0.0
        self._last_price: float = 0.0

    @property
    def venues(self) -> Dict[str, Venue]:
        """Configured venues keyed by venue id."""
        return dict(self._venues)

    def _score_one(self, venue: Venue, order_qty: float, price: float) -> float:
        cost = venue_cost(venue, order_qty, price)
        # Normalise by per-share notional so score is comparable across sizes.
        per_share = cost / max(abs(order_qty), 1e-9)
        return per_share / max(float(venue.liquidity_score), 1e-9)

    def score_venue(
        self,
        order_qty: Number,
        price: Number,
        venue_id: Optional[str] = None,
    ) -> Union[float, Dict[str, float]]:
        """Score venue(s) for a prospective order.

        Args:
            order_qty: Order quantity (shares).
            price: Reference price.
            venue_id: If given, score only that venue; else score all.

        Returns:
            Single score float, or dict of venue_id -> score (lower better).
        """
        qty = _to_float(order_qty)
        px = _to_float(price)
        if qty <= 0 or px <= 0:
            raise ValueError("order_qty and price must be positive.")
        self._last_qty, self._last_price = qty, px
        if venue_id is not None:
            venue = self._venues.get(venue_id)
            if venue is None:
                raise KeyError(f"unknown venue: {venue_id!r}")
            return self._score_one(venue, qty, px)
        return {vid: self._score_one(v, qty, px) for vid, v in self._venues.items()}

    def best_venue(
        self,
        order_qty: Optional[Number] = None,
        price: Optional[Number] = None,
        order: Optional[Union[Mapping, OrderRequest, Tuple, List]] = None,
    ) -> str:
        """Return the venue id with the lowest score.

        Accepts (order_qty, price), an order mapping, or falls back to the
        most recently scored order.
        """
        if order is not None:
            req = _parse_order(order)
            qty, px = req.qty, req.price
        elif order_qty is not None and price is not None:
            qty, px = _to_float(order_qty), _to_float(price)
        elif self._last_qty > 0 and self._last_price > 0:
            qty, px = self._last_qty, self._last_price
        else:
            raise ValueError("best_venue() needs (order_qty, price) or order=.")
        scores = self.score_venue(qty, px)
        assert isinstance(scores, dict)
        return min(scores, key=lambda k: scores[k])

    def route(
        self, order: Union[Mapping, OrderRequest, Tuple, List]
    ) -> List[Tuple[str, float]]:
        """Split a parent order into (venue_id, qty) child allocations.

        Allocations sum to the parent qty (within float rounding); the
        remainder goes to the best venue so nothing is lost.
        """
        req = _parse_order(order)
        qty, px = req.qty, req.price
        if qty <= 0 or px <= 0:
            raise ValueError("order qty and price must be positive.")
        self._last_qty, self._last_price = qty, px
        scores = self.score_venue(qty, px)
        assert isinstance(scores, dict)
        weights: Dict[str, float] = {}
        for vid, venue in self._venues.items():
            w = float(venue.liquidity_score) / max(scores[vid], 1e-12)
            weights[vid] = w
        total = sum(weights.values()) or 1.0
        ranked = sorted(weights, key=lambda k: weights[k], reverse=True)
        splits: List[Tuple[str, float]] = []
        remaining = qty
        for i, vid in enumerate(ranked):
            if i == len(ranked) - 1:
                alloc = remaining
            else:
                alloc = round(qty * weights[vid] / total, 6)
                alloc = min(alloc, remaining)
            if alloc > 0:
                splits.append((vid, float(alloc)))
                remaining = round(remaining - alloc, 6)
        if remaining > 1e-9:  # rounding dust -> best venue
            best = self.best_venue(qty, px)
            for i, (vid, q) in enumerate(splits):
                if vid == best:
                    splits[i] = (vid, q + remaining)
                    break
            else:
                splits.append((best, remaining))
        return splits
