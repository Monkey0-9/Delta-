"""Venue models for smart order routing (DELTA OS).

Conventions: dataclasses, Decimal-optional numeric inputs, stdlib only.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, Union

__all__ = ["Venue", "VENUES", "venue_cost"]

Number = Union[int, float, Decimal]


@dataclass(frozen=True, slots=True)
class Venue:
    """Execution venue descriptor.

    Attributes:
        id: Venue identifier (e.g. "NYSE").
        fee_bps: Taker fee in basis points (negative = rebate).
        latency_us: Mean latency in microseconds.
        liquidity_score: Relative liquidity in (0, 1]; higher is deeper.
    """

    id: str
    fee_bps: float
    latency_us: float
    liquidity_score: float

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("venue id must be non-empty.")
        if not 0.0 < self.liquidity_score <= 1.0:
            raise ValueError("liquidity_score must be in (0, 1].")
        if self.latency_us < 0:
            raise ValueError("latency_us must be non-negative.")


VENUES: Dict[str, Venue] = {
    "NYSE": Venue(id="NYSE", fee_bps=0.30, latency_us=120.0, liquidity_score=0.95),
    "NASDAQ": Venue(id="NASDAQ", fee_bps=0.30, latency_us=110.0, liquidity_score=0.95),
    "ARCA": Venue(id="ARCA", fee_bps=0.28, latency_us=130.0, liquidity_score=0.85),
    "BATS": Venue(id="BATS", fee_bps=0.25, latency_us=90.0, liquidity_score=0.80),
    "IEX": Venue(id="IEX", fee_bps=0.10, latency_us=350.0, liquidity_score=0.60),
    "DARK": Venue(id="DARK", fee_bps=0.05, latency_us=200.0, liquidity_score=0.50),
}


def venue_cost(venue: Venue, qty: Union[Number, str], price: Union[Number, str]) -> float:
    """Estimate all-in execution cost in currency units.

    Cost = notional * fee_bps / 1e4 + latency penalty scaled by notional,
    discounted by venue liquidity. Lower is cheaper.

    Args:
        venue: Venue to score.
        qty: Order quantity (shares, always taken as abs).
        price: Reference price per share.

    Returns:
        Estimated cost as float (>= 0 for positive fees).
    """
    q = abs(float(qty))
    p = float(price)
    if q <= 0 or p <= 0:
        raise ValueError("qty and price must be positive.")
    notional = q * p
    fee = notional * float(venue.fee_bps) / 10_000.0
    # Latency penalty: 1 microsecond ~= 0.001 bps of notional (deterministic).
    latency = notional * float(venue.latency_us) * 1e-3 / 10_000.0
    # Thin venues cost more (price impact proxy): scale by 1 / liquidity.
    impact = notional * (1.0 - float(venue.liquidity_score)) * 0.5 / 10_000.0
    return float(fee + latency + impact)
