"""FINAGENT horizon selector (Week 1).

Maps trader language + mandate horizons to the engine that must answer.
Different horizons need different models/features/validation - never reuse
a short-term trading model for a long-term investment question.
"""
from __future__ import annotations

from dataclasses import dataclass

from decision.horizon import DecisionHorizon


@dataclass(frozen=True, slots=True)
class HorizonSelection:
    key: str  # today | week | month | year
    decision_horizon: DecisionHorizon
    engines: tuple[str, ...]
    abstention_allowed: bool = True


_MAP: tuple[tuple[str, HorizonSelection], ...] = (
    ("intraday", HorizonSelection("today", DecisionHorizon.INTRADAY, ("short_horizon", "regime", "liquidity", "execution"), True)),
    ("today", HorizonSelection("today", DecisionHorizon.INTRADAY, ("short_horizon", "regime", "liquidity", "execution"), True)),
    ("1-5 days", HorizonSelection("week", DecisionHorizon.SHORT_TERM, ("momentum", "trend", "mean_reversion", "events", "regime"), True)),
    ("week", HorizonSelection("week", DecisionHorizon.SHORT_TERM, ("momentum", "trend", "mean_reversion", "events", "regime"), True)),
    ("1-4 weeks", HorizonSelection("month", DecisionHorizon.MEDIUM_TERM, ("macro_regime", "earnings", "factors", "rates_credit"), True)),
    ("month", HorizonSelection("month", DecisionHorizon.MEDIUM_TERM, ("macro_regime", "earnings", "factors", "rates_credit"), True)),
    ("1-6 months", HorizonSelection("month", DecisionHorizon.MEDIUM_TERM, ("macro_regime", "earnings", "factors", "rates_credit"), True)),
    ("1-3 years", HorizonSelection("year", DecisionHorizon.LONG_TERM, ("fundamentals", "valuation", "factor_exposure", "scenarios"), True)),
    ("3-10 years", HorizonSelection("year", DecisionHorizon.LONG_TERM, ("fundamentals", "valuation", "factor_exposure", "scenarios"), True)),
    ("year", HorizonSelection("year", DecisionHorizon.LONG_TERM, ("fundamentals", "valuation", "factor_exposure", "scenarios"), True)),
    ("mixed", HorizonSelection("month", DecisionHorizon.MEDIUM_TERM, ("multi_horizon_arbitration",), True)),
)


class HorizonSelector:
    def select(self, text: str) -> HorizonSelection:
        t = (text or "").strip().lower()
        # Longest (most specific) needle wins: "1-4 weeks" must beat bare "week".
        for needle, sel in sorted(_MAP, key=lambda kv: -len(kv[0])):
            if needle in t:
                return sel
        # Conservative default: medium-term with arbitration, abstention on.
        return HorizonSelection(
            "month", DecisionHorizon.MEDIUM_TERM, ("multi_horizon_arbitration",), True
        )

    def for_goal(self, goal: str) -> HorizonSelection:
        g = (goal or "").lower()
        if g in ("today", "portfolio_review", "stress_test"):
            return HorizonSelection("today", DecisionHorizon.INTRADAY, ("short_horizon", "regime", "liquidity", "execution"), True)
        if g == "week":
            return self.select("week")
        if g == "month":
            return self.select("month")
        if g in ("year", "auto_manage", "research", "analyze_asset"):
            return self.select("year") if g == "year" else self.select("mixed")
        return self.select(g)
