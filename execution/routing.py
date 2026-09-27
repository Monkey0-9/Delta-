"""Paper venue router: deterministic venue selection (paper/sim only).

No live venues exist in this build; any non-paper mode is rejected so a
routing decision can never escape the governed paper path.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


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
