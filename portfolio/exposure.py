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
        gross = portfolio.position_market_value

        equity = portfolio.equity

        if equity == Decimal("0"):
            leverage = Decimal("0")
        else:
            leverage = gross / equity

        return PortfolioExposure(
            gross_exposure=gross,
            net_exposure=gross,
            leverage=leverage,
        )