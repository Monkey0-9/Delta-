from __future__ import annotations

from decimal import Decimal

from .scenario import ScenarioFactor, ScenarioType, StressScenario


class ScenarioGenerator:
    """
    Deterministic stress-scenario generator.

    The generator contains no hidden random state.
    Identical inputs produce identical scenarios.
    """

    @staticmethod
    def equity_crash(
        scenario_id: str,
        severity: Decimal = Decimal("0.20"),
    ) -> StressScenario:
        severity = min(Decimal("1"), abs(severity))

        return StressScenario(
            scenario_id=scenario_id,
            scenario_type=ScenarioType.EQUITY_CRASH,
            name="Broad equity market crash",
            severity=severity,
            factors=(
                ScenarioFactor(
                    name="equity_return",
                    shock=-severity,
                ),
                ScenarioFactor(
                    name="volatility",
                    shock=Decimal("0.50"),
                ),
                ScenarioFactor(
                    name="liquidity",
                    shock=Decimal("-0.30"),
                ),
            ),
        )

    @staticmethod
    def rate_shock(
        scenario_id: str,
        shock: Decimal = Decimal("0.02"),
    ) -> StressScenario:
        return StressScenario(
            scenario_id=scenario_id,
            scenario_type=ScenarioType.RATE_SHOCK,
            name="Parallel interest-rate shock",
            severity=min(
                Decimal("1"),
                abs(shock) / Decimal("0.10"),
            ),
            factors=(
                ScenarioFactor(
                    name="interest_rate",
                    shock=shock,
                    unit="absolute",
                ),
            ),
        )

    @staticmethod
    def liquidity_shock(
        scenario_id: str,
        severity: Decimal = Decimal("0.40"),
    ) -> StressScenario:
        severity = min(Decimal("1"), abs(severity))

        return StressScenario(
            scenario_id=scenario_id,
            scenario_type=ScenarioType.LIQUIDITY_SHOCK,
            name="Market liquidity deterioration",
            severity=severity,
            factors=(
                ScenarioFactor(
                    name="liquidity",
                    shock=-severity,
                ),
                ScenarioFactor(
                    name="spread",
                    shock=severity,
                ),
                ScenarioFactor(
                    name="market_impact",
                    shock=severity,
                ),
            ),
        )

    @staticmethod
    def multi_factor(
        scenario_id: str,
        equity_shock: Decimal,
        volatility_shock: Decimal,
        liquidity_shock: Decimal,
        rate_shock: Decimal = Decimal("0"),
    ) -> StressScenario:
        severity = min(
            Decimal("1"),
            max(
                abs(equity_shock),
                abs(volatility_shock),
                abs(liquidity_shock),
                abs(rate_shock),
            ),
        )

        return StressScenario(
            scenario_id=scenario_id,
            scenario_type=ScenarioType.MULTI_FACTOR,
            name="Multi-factor systemic stress",
            severity=severity,
            factors=(
                ScenarioFactor(
                    name="equity_return",
                    shock=equity_shock,
                ),
                ScenarioFactor(
                    name="volatility",
                    shock=volatility_shock,
                ),
                ScenarioFactor(
                    name="liquidity",
                    shock=liquidity_shock,
                ),
                ScenarioFactor(
                    name="interest_rate",
                    shock=rate_shock,
                ),
            ),
        )