from __future__ import annotations

import re

from .domain_guard import FinanceDomainGuard
from .intent import (
    Domain,
    FinanceIntent,
    Horizon,
    Intent,
    Objective,
)


_HORIZON_PATTERNS: tuple[tuple[Horizon, tuple[str, ...]], ...] = (
    (
        Horizon.TODAY,
        (
            "today",
            "for today",
            "this day",
            "intraday",
            "intra day",
        ),
    ),
    (
        Horizon.WEEK,
        (
            "this week",
            "for this week",
            "next week",
            "weekly",
            "week",
        ),
    ),
    (
        Horizon.MONTH,
        (
            "this month",
            "for this month",
            "next month",
            "monthly",
            "month",
        ),
    ),
    (
        Horizon.LONG_TERM,
        (
            "long term",
            "long-term",
            "longterm",
            "three years",
            "5 years",
            "five years",
            "10 years",
            "ten years",
        ),
    ),
    (
        Horizon.YEAR,
        (
            "this year",
            "for this year",
            "next year",
            "yearly",
            "year",
        ),
    ),
)


_SYMBOL_RE = re.compile(
    r"(?<![A-Za-z])\$?([A-Z]{1,6})(?![A-Za-z])"
)


_STOPWORDS = frozenset(
    {
        "I",
        "A",
        "THE",
        "WHAT",
        "WHICH",
        "IS",
        "FOR",
        "TODAY",
        "THIS",
        "WEEK",
        "MONTH",
        "YEAR",
        "HOW",
        "CAN",
        "SHOULD",
        "DO",
        "WE",
        "MY",
        "BEST",
        "OR",
        "AND",
        "TO",
        "BUY",
        "SELL",
    }
)


class FinanceCommandRouter:
    """Pure request -> intent translation.

    No network calls.
    No broker calls.
    No order placement.
    No LLM calls.
    """

    def route(self, text: str) -> FinanceIntent:
        raw = text.strip()
        lowered = raw.casefold()

        if lowered in {"exit", "quit"}:
            return FinanceIntent(
                raw_text=raw,
                domain=Domain.FINANCE,
                intent=Intent.STOP,
                confidence=1.0,
            )

        if lowered in {"help", "?", "commands"}:
            return FinanceIntent(
                raw_text=raw,
                domain=Domain.FINANCE,
                intent=Intent.HELP,
                confidence=1.0,
            )

        # Handle conversational intents (check these BEFORE domain classification)
        if lowered in {"hi", "hello", "hey", "greetings", "good morning", "good afternoon", "good evening", "yo", "sup"}:
            return FinanceIntent(
                raw_text=raw,
                domain=Domain.FINANCE,
                intent=Intent.GREETING,
                confidence=1.0,
            )

        # More flexible date/time matching with common typos
        date_time_keywords = [
            "what date", "what time", "today date", "current date", "current time",
            "what day", "what's the date", "what's the time", "date today", "time now",
            "what day is it", "what is the date", "what is the time", "today's date",
            "today is", "what is today", "todays date", "wat date", "wht date",
            "dtae", "date time", "show date", "show time"
        ]
        if any(keyword in lowered for keyword in date_time_keywords):
            return FinanceIntent(
                raw_text=raw,
                domain=Domain.FINANCE,
                intent=Intent.DATE_TIME,
                confidence=1.0,
            )

        # Investor perspective queries - for crorepati/millionaire mindset
        investor_keywords = [
            "as an investor", "investor perspective", "if i were", "as a crorepati",
            "as a millionaire", "crore investor", "million investor", "wealth",
            "portfolio mindset", "investor mindset", "how should i think",
            "investor psychology", "wealth building", "long term investor"
        ]
        if any(keyword in lowered for keyword in investor_keywords):
            return FinanceIntent(
                raw_text=raw,
                domain=Domain.FINANCE,
                intent=Intent.INVESTOR_PERSPECTIVE,
                confidence=1.0,
            )

        # Market sentiment and macro queries
        sentiment_keywords = [
            "market sentiment", "how is the market", "market mood", "bullish bearish",
            "market outlook", "macro view", "economic outlook", "market conditions",
            "what's happening in market", "market trend", "overall market"
        ]
        if any(keyword in lowered for keyword in sentiment_keywords):
            return FinanceIntent(
                raw_text=raw,
                domain=Domain.FINANCE,
                intent=Intent.MARKET_SENTIMENT,
                confidence=1.0,
            )

        # Strategy discussion queries
        strategy_keywords = [
            "investment strategy", "trading strategy", "my strategy", "strategy help",
            "best strategy", "strategy advice", "how to invest", "investment approach",
            "trading approach", "portfolio strategy"
        ]
        if any(keyword in lowered for keyword in strategy_keywords):
            return FinanceIntent(
                raw_text=raw,
                domain=Domain.FINANCE,
                intent=Intent.STRATEGY_DISCUSSION,
                confidence=1.0,
            )

        # General info queries
        general_info_keywords = [
            "how are you", "what can you do", "tell me about yourself", "who are you",
            "what are you", "what is delta", "introduce yourself", "what do you do",
            "your capabilities", "help me", "what can you", "tell me about delta",
            "delta capabilities", "about delta"
        ]
        if any(keyword in lowered for keyword in general_info_keywords):
            return FinanceIntent(
                raw_text=raw,
                domain=Domain.FINANCE,
                intent=Intent.GENERAL_INFO,
                confidence=1.0,
            )

        domain = FinanceDomainGuard.classify(raw)

        if domain != Domain.FINANCE:
            return FinanceIntent(
                raw_text=raw,
                domain=domain,
                intent=Intent.UNKNOWN,
                confidence=0.99,
            )

        horizon = self._resolve_horizon(lowered)
        objective = self._resolve_objective(lowered)
        intent = self._resolve_intent(lowered)

        symbols = self._extract_symbols(raw)

        requires_fresh_data = intent in {
            Intent.MARKET_UPDATE,
            Intent.NEWS,
            Intent.OPPORTUNITIES,
            Intent.TRADE_DECISION,
            Intent.ANALYZE_ASSET,
            Intent.COMPARE,
            Intent.RISK,
            Intent.STRESS,
            Intent.SIMULATE,
        }

        requires_portfolio = intent in {
            Intent.PORTFOLIO,
            Intent.RISK,
            Intent.STRESS,
            Intent.REBALANCE if False else Intent.PORTFOLIO,
            Intent.TRADE_DECISION,
            Intent.EXECUTE,
            Intent.AUTOMATION,
        }

        execution_requested = intent == Intent.EXECUTE

        automation_requested = intent == Intent.AUTOMATION

        requires_broker = intent in {
            Intent.EXECUTE,
            Intent.BROKER_CONNECT,
            Intent.BROKER_STATUS,
            Intent.AUTOMATION,
        }

        return FinanceIntent(
            raw_text=raw,
            domain=domain,
            intent=intent,
            horizon=horizon,
            objective=objective,
            symbols=symbols,
            requires_fresh_data=requires_fresh_data,
            requires_portfolio=requires_portfolio,
            requires_broker=requires_broker,
            execution_requested=execution_requested,
            automation_requested=automation_requested,
            confidence=self._confidence(intent, horizon),
        )

    @staticmethod
    def _resolve_horizon(text: str) -> Horizon:
        for horizon, patterns in _HORIZON_PATTERNS:
            if any(pattern in text for pattern in patterns):
                return horizon

        return Horizon.UNSPECIFIED

    @staticmethod
    def _resolve_objective(text: str) -> Objective:
        if "highest return" in text or "maximum return" in text:
            return Objective.EXPECTED_RETURN

        if (
            "risk adjusted" in text
            or "risk-adjusted" in text
            or "best risk" in text
        ):
            return Objective.RISK_ADJUSTED

        if (
            "lowest risk" in text
            or "lower risk" in text
            or "least risk" in text
        ):
            return Objective.LOW_RISK

        if (
            "diversif" in text
            or "uncorrelated" in text
        ):
            return Objective.DIVERSIFICATION

        if "liquid" in text or "liquidity" in text:
            return Objective.LIQUIDITY

        if "execution" in text or "cheapest to execute" in text:
            return Objective.EXECUTION

        if "hedge" in text:
            return Objective.HEDGE

        return Objective.MANDATE_DEFAULT

    @staticmethod
    def _resolve_intent(text: str) -> Intent:
        # Check for trade decision patterns first (more specific)
        if (
            "best trade" in text
            or "best stock" in text
            or "what should i trade" in text
            or "what should i buy" in text
            or "what should i hold" in text
            or "what should i consider" in text
            or "opportunities" in text
            or "opportunity" in text
            or "trade today" in text
        ):
            return Intent.TRADE_DECISION

        if "market update" in text or "what changed" in text:
            return Intent.MARKET_UPDATE

        if "news" in text:
            return Intent.NEWS

        if "portfolio" in text and (
            "risk" in text
            or "exposure" in text
            or "manage" in text
        ):
            return Intent.PORTFOLIO

        if "stress" in text:
            return Intent.STRESS

        if "simulate" in text or "what if" in text:
            return Intent.SIMULATE

        if "compare" in text:
            return Intent.COMPARE

        if text.startswith("analyze ") or "analyze " in text:
            return Intent.ANALYZE_ASSET

        if "risk" in text:
            return Intent.RISK

        if (
            "research" in text
            or "study" in text
            or "quantitative" in text
        ):
            return Intent.RESEARCH

        if (
            "connect broker" in text
            or "connect my broker" in text
            or text == "connect"
        ):
            return Intent.BROKER_CONNECT

        if (
            "broker status" in text
            or "broker health" in text
            or "is my broker" in text
        ):
            return Intent.BROKER_STATUS

        if (
            "automate" in text
            or "automation" in text
            or "manage automatically" in text
            or "monitor automatically" in text
        ):
            return Intent.AUTOMATION

        if (
            "execute" in text
            or "place the order" in text
            or "place an order" in text
        ):
            return Intent.EXECUTE

        if "failure" in text or "why did we lose" in text:
            return Intent.FAILURES

        if text == "status" or "system status" in text:
            return Intent.STATUS

        if text in {"stop", "stop trading", "kill", "kill switch"}:
            return Intent.STOP

        return Intent.RESEARCH

    @staticmethod
    def _extract_symbols(text: str) -> tuple[str, ...]:
        symbols: list[str] = []

        for match in _SYMBOL_RE.finditer(text):
            symbol = match.group(1)

            if symbol in _STOPWORDS:
                continue

            if symbol not in symbols:
                symbols.append(symbol)

        return tuple(symbols)

    @staticmethod
    def _confidence(
        intent: Intent,
        horizon: Horizon,
    ) -> float:
        score = 0.65

        if intent != Intent.UNKNOWN:
            score += 0.15

        if horizon != Horizon.UNSPECIFIED:
            score += 0.10

        return min(score, 0.95)
    
    DECISION_PHRASES: tuple[str, ...] = (
    "what should i trade",
    "what should i buy",
    "what should i sell",
    "what should i hold",
    "what should i consider",
    "what should i invest",
    "what should i invest in",
    "what should i own",
    "should i trade",
    "should i buy",
    "should i sell",
    "should i hold",
    "should i reduce",
    "should i increase",
    "should i rebalance",
    "manage my portfolio",
    "find opportunities",
    "find trades",
    "best trade",
    "trade today",
    "trade this week",
    "trade this month",
)