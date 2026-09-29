"""Execution routing package (DELTA OS).

New API: Venue / VENUES / venue_cost / SmartOrderRouter.
Legacy paper-venue API (execution/routing.py): PAPER_VENUES / Route /
route_order / score_venue / best_venue is re-exported here so existing
imports keep working after the module -> package migration.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Tuple

from .venue_models import VENUES, Venue, venue_cost
from .smart_order_router import OrderRequest, SmartOrderRouter

__all__ = [
    # New SOR API
    "Venue",
    "VENUES",
    "venue_cost",
    "SmartOrderRouter",
    "OrderRequest",
    # Legacy paper-venue API (kept for backwards compatibility)
    "PaperVenue",
    "PAPER_VENUES",
    "Route",
    "route_order",
    "score_venue",
    "best_venue",
]


# --- Legacy paper-venue API (verbatim from execution/routing.py) ---
@dataclass(frozen=True, slots=True)
class PaperVenue:
    """Legacy paper venue model: economics + latency + reliability."""

    name: str
    maker_fee_bps: Decimal = Decimal("0")
    taker_fee_bps: Decimal = Decimal("0")
    latency_us: Decimal = Decimal("50")
    reliability: Decimal = Decimal("1")


PAPER_VENUES: Tuple[PaperVenue, ...] = (
    PaperVenue("paper-venue", Decimal("-0.2"), Decimal("0.3"), Decimal("50"), Decimal("1")),
    PaperVenue("paper-venue-2", Decimal("0"), Decimal("0.25"), Decimal("120"), Decimal("0.999")),
)


def score_venue(venue: PaperVenue, quantity: Decimal, urgency: Decimal = Decimal("0.5")) -> Decimal:
    """Route score: lower cost + lower latency wins; reliability penalizes."""
    if quantity <= 0:
        raise ValueError("quantity must be positive.")
    cost = venue.taker_fee_bps + urgency * venue.latency_us / Decimal("1000")
    return cost + (Decimal("1") - venue.reliability) * Decimal("100")


def best_venue(quantity: Decimal, urgency: Decimal = Decimal("0.5")) -> PaperVenue:
    """Cheapest legacy paper venue for the given quantity/urgency."""
    return min(PAPER_VENUES, key=lambda v: score_venue(v, quantity, urgency))


@dataclass(frozen=True, slots=True)
class Route:
    venue: str
    slices: int
    reason: str


def route_order(
    *,
    quantity: Decimal,
    adv: Decimal,
    mode: str = "paper",
    max_slice_adv: Decimal = Decimal("0.1"),
) -> Route:
    """Deterministic paper-only router; rejects any non-paper mode."""
    if quantity <= 0 or adv <= 0:
        raise ValueError("quantity/adv must be positive.")
    if mode != "paper":
        raise ValueError(f"routing denied: non-paper mode {mode!r}.")
    participation = quantity / adv
    if participation <= max_slice_adv:
        return Route("paper-venue", 1, "within single-slice participation")
    slices = int((participation / max_slice_adv).to_integral_value(rounding="ROUND_CEILING"))
    return Route("paper-venue", max(2, slices), f"split for participation {participation:.3f}")
