"""Paper venue router: deterministic venue selection (paper/sim only).

No live venues exist in this build; any non-paper mode is rejected so a
routing decision can never escape the governed paper path.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class Venue:
    """W181-W190 venue model: economics + latency + reliability for route scoring."""
    name: str
    maker_fee_bps: Decimal = Decimal("0")
    taker_fee_bps: Decimal = Decimal("0")
    latency_us: Decimal = Decimal("50")
    reliability: Decimal = Decimal("1")


PAPER_VENUES: tuple[Venue, ...] = (
    Venue("paper-venue", Decimal("-0.2"), Decimal("0.3"), Decimal("50"), Decimal("1")),
    Venue("paper-venue-2", Decimal("0"), Decimal("0.25"), Decimal("120"), Decimal("0.999")),
)


def score_venue(venue: Venue, quantity: Decimal, urgency: Decimal = Decimal("0.5")) -> Decimal:
    """Route score: lower cost + lower latency wins; reliability penalizes."""
    if quantity <= 0:
        raise ValueError("quantity must be positive.")
    cost = venue.taker_fee_bps + urgency * venue.latency_us / Decimal("1000")
    return cost + (Decimal("1") - venue.reliability) * Decimal("100")


def best_venue(quantity: Decimal, urgency: Decimal = Decimal("0.5")) -> Venue:
    return min(PAPER_VENUES, key=lambda v: score_venue(v, quantity, urgency))


@dataclass(frozen=True, slots=True)
class Route:
    venue: str
    slices: int
    reason: str


def route_order(
    *, quantity: Decimal, adv: Decimal, mode: str = "paper", max_slice_adv: Decimal = Decimal("0.1")
) -> Route:
    if quantity <= 0 or adv <= 0:
        raise ValueError("quantity/adv must be positive.")
    if mode != "paper":
        raise ValueError(f"routing denied: non-paper mode {mode!r}.")
    participation = quantity / adv
    if participation <= max_slice_adv:
        return Route("paper-venue", 1, "within single-slice participation")
    slices = int((participation / max_slice_adv).to_integral_value(rounding="ROUND_CEILING"))
    return Route("paper-venue", max(2, slices), f"split for participation {participation:.3f}")
