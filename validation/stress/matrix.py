"""Canonical stress matrix: mild shocks must be survived, severe must be flagged.

Survival tier (severity <= 0.20): no MAX_DRAWDOWN / MAX_LEVERAGE breach.
Detection tier (severity > 0.20): breaches must be reported (risk observability).
Deterministic: fixed scenarios, fixed portfolio, no randomness.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from simulation.scenarios.scenario import ScenarioFactor, ScenarioType, StressScenario
from validation.stress.evaluator import StressEvaluator, StressLimits
from validation.stress.result import StressResult


@dataclass(frozen=True, slots=True)
class ShockVerdict:
    scenario_id: str
    tier: str  # "survival" | "detection"
    passed: bool
    breaches: tuple[str, ...]
    portfolio_return: Decimal


@dataclass(frozen=True, slots=True)
class MatrixReport:
    passed: bool
    verdicts: tuple[ShockVerdict, ...]
    failed_shocks: tuple[str, ...]


def _sc(sid: str, stype: ScenarioType, name: str, severity: str, factors: tuple[ScenarioFactor, ...]) -> StressScenario:
    return StressScenario(
        scenario_id=sid,
        scenario_type=stype,
        name=name,
        severity=Decimal(severity),
        factors=factors,
    )


def canonical_matrix() -> tuple[StressScenario, ...]:
    return (
        _sc("VOL-20", ScenarioType.VOLATILITY_SHOCK, "vol spike mild", "0.20", (
            ScenarioFactor("volatility", Decimal("0.40")),)),
        _sc("VOL-80", ScenarioType.VOLATILITY_SHOCK, "vol spike severe", "0.80", (
            ScenarioFactor("volatility", Decimal("1.50")),
            ScenarioFactor("equity_return", Decimal("-0.10")),)),
        _sc("RATE-10", ScenarioType.RATE_SHOCK, "rate +100bp", "0.10", (
            ScenarioFactor("interest_rate", Decimal("0.01"), "absolute"),
            ScenarioFactor("equity_return", Decimal("-0.03")),)),
        _sc("RATE-60", ScenarioType.RATE_SHOCK, "rate +500bp", "0.60", (
            ScenarioFactor("interest_rate", Decimal("0.05"), "absolute"),
            ScenarioFactor("equity_return", Decimal("-0.18")),
            ScenarioFactor("volatility", Decimal("0.60")),)),
        _sc("CRASH-15", ScenarioType.EQUITY_CRASH, "equity -15%", "0.15", (
            ScenarioFactor("equity_return", Decimal("-0.15")),
            ScenarioFactor("volatility", Decimal("0.40")),
            ScenarioFactor("liquidity", Decimal("-0.20")),)),
        _sc("CRASH-40", ScenarioType.EQUITY_CRASH, "equity -40%", "0.40", (
            ScenarioFactor("equity_return", Decimal("-0.40")),
            ScenarioFactor("volatility", Decimal("1.20")),
            ScenarioFactor("liquidity", Decimal("-0.60")),)),
        _sc("CREDIT-50", ScenarioType.CREDIT_SPREAD_SHOCK, "credit blowout", "0.50", (
            ScenarioFactor("equity_return", Decimal("-0.22")),
            ScenarioFactor("volatility", Decimal("0.80")),
            ScenarioFactor("liquidity", Decimal("-0.50")),)),
        _sc("LIQ-70", ScenarioType.LIQUIDITY_SHOCK, "liquidity freeze", "0.70", (
            ScenarioFactor("liquidity", Decimal("-0.70")),
            ScenarioFactor("volatility", Decimal("0.50")),
            ScenarioFactor("equity_return", Decimal("-0.10")),)),
        _sc("CORR-60", ScenarioType.CORRELATION_BREAK, "correlation convergence", "0.60", (
            ScenarioFactor("equity_return", Decimal("-0.20")),
            ScenarioFactor("volatility", Decimal("0.90")),)),
        _sc("EXEC-30", ScenarioType.CUSTOM, "execution degradation", "0.30", (
            ScenarioFactor("liquidity", Decimal("-0.35")),
            ScenarioFactor("equity_return", Decimal("-0.05")),)),
        _sc("DATA-50", ScenarioType.CUSTOM, "data outage drift", "0.50", (
            ScenarioFactor("volatility", Decimal("0.70")),
            ScenarioFactor("liquidity", Decimal("-0.40")),)),
    )


_HARD_BREACHES = frozenset({"MAX_DRAWDOWN", "MAX_LEVERAGE"})


def run_matrix(
    *,
    portfolio_value: Decimal = Decimal("100000"),
    gross_exposure: Decimal = Decimal("80000"),
    net_exposure: Decimal = Decimal("20000"),
    leverage: Decimal = Decimal("0.8"),
    positions: dict[str, Decimal] | None = None,
    limits: StressLimits | None = None,
) -> MatrixReport:
    evaluator = StressEvaluator(limits=limits)
    pos = positions or {"AAA": Decimal("0.5"), "BBB": Decimal("0.3")}
    verdicts: list[ShockVerdict] = []
    for scenario in canonical_matrix():
        result: StressResult = evaluator.evaluate(
            scenario,
            portfolio_value=portfolio_value,
            gross_exposure=gross_exposure,
            net_exposure=net_exposure,
            leverage=leverage,
            positions=pos,
        )
        hard = tuple(b for b in result.risk_limit_breaches if b in _HARD_BREACHES)
        if scenario.severity <= Decimal("0.20"):
            passed = not hard
            tier = "survival"
        else:
            passed = bool(result.risk_limit_breaches) or result.portfolio_return <= Decimal("0")
            tier = "detection"
        verdicts.append(ShockVerdict(scenario.scenario_id, tier, passed, result.risk_limit_breaches, result.portfolio_return))
    failed = tuple(v.scenario_id for v in verdicts if not v.passed)
    return MatrixReport(passed=not failed, verdicts=tuple(verdicts), failed_shocks=failed)
