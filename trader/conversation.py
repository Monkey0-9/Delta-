"""FINAGENT conversational manager (Week 1).

Deterministic, rule-based dialogue state machine. No LLM calls, no trading.
Turns natural language + menu choices into a structured trader goal.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class TraderGoal(str, Enum):
    TODAY = "today"
    WEEK = "week"
    MONTH = "month"
    YEAR = "year"
    PORTFOLIO_REVIEW = "portfolio_review"
    ANALYZE_ASSET = "analyze_asset"
    STRESS_TEST = "stress_test"
    AUTO_MANAGE = "auto_manage"
    RESEARCH = "research"


MENU: tuple[tuple[str, TraderGoal, str], ...] = (
    ("1", TraderGoal.TODAY, "Find trades for today"),
    ("2", TraderGoal.WEEK, "Find opportunities for this week"),
    ("3", TraderGoal.MONTH, "Find medium-term opportunities"),
    ("4", TraderGoal.PORTFOLIO_REVIEW, "Review my portfolio"),
    ("5", TraderGoal.YEAR, "Find long-term investments"),
    ("6", TraderGoal.ANALYZE_ASSET, "Analyze a stock/ETF"),
    ("7", TraderGoal.STRESS_TEST, "Stress-test my portfolio"),
    ("8", TraderGoal.AUTO_MANAGE, "Manage my portfolio automatically"),
    ("9", TraderGoal.RESEARCH, "Research something"),
)

_GREETING = (
    "Good morning.\n"
    "What are you looking to do today?\n"
    "1. Find trades for today\n"
    "2. Find opportunities for this week\n"
    "3. Find medium-term opportunities\n"
    "4. Review my portfolio\n"
    "5. Find long-term investments\n"
    "6. Analyze a stock/ETF\n"
    "7. Stress-test my portfolio\n"
    "8. Manage my portfolio automatically\n"
    "9. Research something\n"
    "Or just tell me what you want in natural language."
)

_KEYWORDS: tuple[tuple[TraderGoal, tuple[str, ...]], ...] = (
    (TraderGoal.STRESS_TEST, ("stress", "volatility increases", "what happens if", "drawdown", "scenario")),
    (TraderGoal.AUTO_MANAGE, ("manage my portfolio", "automatically", "rebalance", "execute this strategy", "autonomous")),
    (TraderGoal.TODAY, ("today", "intraday", "day trade", "stay in cash", "should i trade")),
    (TraderGoal.WEEK, ("this week", "week", "1-5 days", "5 days", "swing")),
    (TraderGoal.MONTH, ("month", "1-4 weeks", "medium", "monthly")),
    (TraderGoal.YEAR, ("year", "long term", "long-term", "3 years", "hold for", "invest for years")),
    (TraderGoal.PORTFOLIO_REVIEW, ("portfolio", "positions", "what do i own", "concentrat", "reduce", "exposure", "risk am i")),
    (TraderGoal.ANALYZE_ASSET, ("analyze", "stock", "etf", "ticker", "nvda", "valuation")),
    (TraderGoal.RESEARCH, ("research", "why", "explain", "what is", "news", "earnings")),
)


@dataclass(frozen=True, slots=True)
class ParsedIntent:
    goal: TraderGoal
    raw_text: str
    confidence: float
    needs_clarification: bool = False


@dataclass
class ConversationState:
    goal: TraderGoal | None = None
    capital_answered: bool = False
    horizon_answered: bool = False
    risk_answered: bool = False
    universe_answered: bool = False
    history: list[str] = field(default_factory=list)


class ConversationManager:
    """Pure dialogue helper used by CLI and future chat transport."""

    def greeting(self) -> str:
        return _GREETING

    def parse(self, text: str) -> ParsedIntent:
        t = (text or "").strip().lower()
        if not t:
            return ParsedIntent(TraderGoal.RESEARCH, text, 0.0, True)
        for key, goal, _label in MENU:
            if t == key or t == key.strip():
                return ParsedIntent(goal, text, 1.0)
        scores: dict[TraderGoal, int] = {}
        for goal, words in _KEYWORDS:
            scores[goal] = sum(1 for w in words if w in t)
        best = max(scores, key=lambda g: scores[g])
        if scores[best] == 0:
            return ParsedIntent(TraderGoal.RESEARCH, text, 0.25, True)
        return ParsedIntent(best, text, min(0.95, 0.55 + 0.1 * scores[best]))

    def next_question(self, state: ConversationState) -> str:
        if state.goal is None:
            return self.greeting()
        if not state.capital_answered:
            return "What capital or portfolio should I consider? (e.g. Rs 10,00,000, or 'use connected account')"
        if not state.horizon_answered:
            return "What is your time horizon? (Intraday / Today / 1-5 days / 1-4 weeks / 1-6 months / 1-3 years / 3-10 years / Mixed)"
        if not state.risk_answered:
            return "What level of risk and loss tolerance should your mandate permit? (conservative / moderate / aggressive + max drawdown %)"
        if not state.universe_answered:
            return "Which assets should I consider? (US equities / Indian equities / ETFs / Bonds / Treasuries / FX / Commodities / Crypto / Multi-asset / Custom)"
        return "Should I analyze your existing portfolio together with new opportunities? (yes/no)"

    def followups_for_goal(self, goal: TraderGoal) -> list[str]:
        base = [
            "Execute #1.",
            "Explain #1.",
            "What if I don't execute #1?",
            "Find an alternative with lower risk.",
            "Don't trade today; just monitor.",
        ]
        if goal == TraderGoal.PORTFOLIO_REVIEW:
            return ["What can I do about concentration?", "Simulate Option A vs B.", "Stress-test this portfolio."]
        if goal == TraderGoal.STRESS_TEST:
            return ["What happens if volatility +30%?", "What is the worst drawdown?", "Which position hurts most?"]
        return base
