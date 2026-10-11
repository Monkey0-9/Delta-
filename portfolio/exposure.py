from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from .state import PortfolioState


@dataclass(frozen=True, slots=True)
class PortfolioExposure:
    gross_exposure: Decimal
    net_exposure: Decimal
    leverage: Decimal


class ExposureCalculator:
    @staticmethod
    def calculate(
        portfolio: PortfolioState,
    ) -> PortfolioExposure:
        # P2: gross is sum-of-abs, net is the signed sum. The position model
        # is long-only today (quantity >= 0 enforced), so the two agree now —
        # but net_exposure=gross hard-codes that assumption and would
        # overstate exposure the day shorts/hedges exist.
        gross = sum(
            (abs(position.market_value) for position in portfolio.positions),
            Decimal("0"),
        )
        net = sum(
            (position.market_value for position in portfolio.positions),
            Decimal("0"),
        )

        equity = portfolio.equity

        if equity == Decimal("0"):
            leverage = Decimal("0")
        else:
            leverage = gross / equity

        return PortfolioExposure(
            gross_exposure=gross,
            net_exposure=net,
            leverage=leverage,
        )