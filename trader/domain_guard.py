from __future__ import annotations

import re

from .intent import Domain


_FINANCE_TERMS = frozenset(
    {
        "trade",
        "trading",
        "invest",
        "investment",
        "portfolio",
        "stock",
        "stocks",
        "share",
        "shares",
        "etf",
        "fund",
        "bond",
        "bonds",
        "treasury",
        "treasuries",
        "option",
        "options",
        "future",
        "futures",
        "forex",
        "fx",
        "crypto",
        "market",
        "markets",
        "equity",
        "equities",
        "commodity",
        "commodities",
        "risk",
        "return",
        "volatility",
        "drawdown",
        "var",
        "cvar",
        "alpha",
        "factor",
        "liquidity",
        "earnings",
        "revenue",
        "valuation",
        "macro",
        "inflation",
        "interest",
        "rates",
        "yield",
        "yield",
        "broker",
        "order",
        "orders",
        "position",
        "positions",
        "rebalance",
        "hedge",
        "pnl",
        "profit",
        "loss",
    }
)

_FINANCE_SYMBOL_RE = re.compile(
    r"(?<![A-Za-z])\$?[A-Z]{1,6}(?![A-Za-z])"
)


class FinanceDomainGuard:
    """Cheap deterministic front-door gate.

    This is intentionally only the first layer. A later model-backed
    classifier can replace/augment it without changing the CLI contract.
    """

    @staticmethod
    def classify(text: str) -> Domain:
        normalized = text.casefold().strip()

        if not normalized:
            return Domain.AMBIGUOUS

        tokens = set(re.findall(r"[a-zA-Z]+", normalized))

        if tokens & _FINANCE_TERMS:
            return Domain.FINANCE

        if _FINANCE_SYMBOL_RE.search(text):
            return Domain.FINANCE

        return Domain.NON_FINANCE