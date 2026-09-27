from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping


class Action(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"
    REDUCE = "REDUCE"


@dataclass(frozen=True, slots=True)
class PortfolioLimits:

    max_position: float
    max_gross: float
    max_net: float
    max_turnover: float


@dataclass(frozen=True, slots=True)
class PortfolioState:

    positions: Mapping[str, float]

    @property
    def gross(self) -> float:
        return sum(
            abs(x)
            for x in self.positions.values()
        )

    @property
    def net(self) -> float:
        return sum(
            self.positions.values()
        )


@dataclass(frozen=True, slots=True)
class CandidateOrder:

    asset: str
    action: Action
    quantity: float
    expected_return: float
    confidence: float

    def signed_quantity(self) -> float:

        if self.action == Action.BUY:
            return self.quantity

        if self.action in (
            Action.SELL,
            Action.REDUCE,
        ):
            return -self.quantity

        return 0.0


class PortfolioDecisionEngine:

    def __init__(
        self,
        limits: PortfolioLimits,
    ):
        self.limits = limits

    def approve(
        self,
        state: PortfolioState,
        order: CandidateOrder,
    ) -> bool:

        if order.quantity <= 0:
            return False

        if order.action == Action.HOLD:
            return False

        if not 0.0 <= order.confidence <= 1.0:
            return False

        current = state.positions.get(
            order.asset,
            0.0,
        )

        proposed = (
            current
            + order.signed_quantity()
        )

        if abs(proposed) > self.limits.max_position:
            return False

        new_positions = dict(
            state.positions
        )

        new_positions[
            order.asset
        ] = proposed

        gross = sum(
            abs(x)
            for x in new_positions.values()
        )

        net = sum(
            new_positions.values()
        )

        turnover = abs(
            order.signed_quantity()
        )

        if gross > self.limits.max_gross:
            return False

        if abs(net) > self.limits.max_net:
            return False

        if turnover > self.limits.max_turnover:
            return False

        return True