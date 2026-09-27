from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Mapping

from simulation.scenarios.scenario import StressScenario
from .result import StressResult


@dataclass(frozen=True, slots=True)
class StressLimits:
    max_drawdown: Decimal = Decimal("-0.20")
    max_leverage: Decimal = Decimal("3")
    max_liquidity_impact: Decimal = Decimal("0.30")


class StressEvaluator:
    """
    Deterministic portfolio stress evaluator.

    Portfolio values are supplied by the caller.
    No broker access.
    """

    def __init__(self, limits: StressLimits | None = None) -> None:
        self._limits = limits or StressLimits()

    def evaluate(
        self,
        scenario: StressScenario,
        *,
        portfolio_value: Decimal,
        gross_exposure: Decimal,
        net_exposure: Decimal,
        leverage: Decimal,
        positions: Mapping[str, Decimal],
    ) -> StressResult:

        if portfolio_value <= 0:
            raise ValueError("portfolio_value must be positive.")

        equity_shock = Decimal("0")
        volatility = Decimal("0")
        liquidity = Decimal("0")

        for factor in scenario.factors:
            if factor.name == "equity_return":
                equity_shock += factor.shock
            elif factor.name == "volatility":
                volatility += factor.shock
            elif factor.name == "liquidity":
                liquidity += factor.shock

        pnl = portfolio_value * equity_shock

        liquidity_impact = abs(liquidity)

        stress_drawdown = min(
            Decimal("0"),
            equity_shock - (volatility * Decimal("0.10")),
        )

        new_gross = gross_exposure * (
            Decimal("1") + volatility * Decimal("0.10")
        )

        new_leverage = new_gross / portfolio_value

        breaches: list[str] = []

        if stress_drawdown < self._limits.max_drawdown:
            breaches.append("MAX_DRAWDOWN")

        if new_leverage > self._limits.max_leverage:
            breaches.append("MAX_LEVERAGE")

        if liquidity_impact > self._limits.max_liquidity_impact:
            breaches.append("LIQUIDITY")

        affected = tuple(
            symbol
            for symbol, weight in positions.items()
            if weight != 0
        )

        confidence = min(
            Decimal("1"),
            Decimal("0.70")
            + abs(scenario.severity) * Decimal("0.20"),
        )

        return StressResult(
            scenario_id=scenario.scenario_id,
            portfolio_pnl=pnl,
            portfolio_return=pnl / portfolio_value,
            max_drawdown=stress_drawdown,
            gross_exposure_before=gross_exposure,
            gross_exposure_after=new_gross,
            net_exposure_before=net_exposure,
            net_exposure_after=net_exposure,
            leverage_before=leverage,
            leverage_after=new_leverage,
            liquidity_impact=liquidity_impact,
            margin_impact=max(Decimal("0"), new_leverage - leverage),
            affected_positions=affected,
            risk_limit_breaches=tuple(breaches),
            confidence=confidence,
        )