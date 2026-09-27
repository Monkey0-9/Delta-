from __future__ import annotations

from trader.command_router import FinanceCommandRouter
from trader.domain_guard import FinanceDomainGuard
from trader.intent import Domain, Horizon, Intent, Objective


def test_finance_domain_detection() -> None:
    assert FinanceDomainGuard.classify(
        "what should I trade today?"
    ) == Domain.FINANCE


def test_non_finance_is_rejected() -> None:
    assert FinanceDomainGuard.classify(
        "write a poem about mountains"
    ) == Domain.NON_FINANCE


def test_today_trade_request() -> None:
    request = FinanceCommandRouter().route(
        "what should I trade today?"
    )

    assert request.domain == Domain.FINANCE
    assert request.intent == Intent.TRADE_DECISION
    assert request.horizon == Horizon.TODAY
    assert request.requires_fresh_data is True


def test_week_request() -> None:
    request = FinanceCommandRouter().route(
        "what opportunities should I consider this week?"
    )

    assert request.intent == Intent.TRADE_DECISION
    assert request.horizon == Horizon.WEEK


def test_month_request() -> None:
    request = FinanceCommandRouter().route(
        "what should I hold this month?"
    )

    assert request.intent == Intent.TRADE_DECISION
    assert request.horizon == Horizon.MONTH


def test_long_term_request() -> None:
    request = FinanceCommandRouter().route(
        "what should I consider for 5 years?"
    )

    assert request.intent == Intent.TRADE_DECISION
    assert request.horizon == Horizon.LONG_TERM


def test_risk_adjusted_objective() -> None:
    request = FinanceCommandRouter().route(
        "which trade has the best risk adjusted opportunity today?"
    )

    assert request.objective == Objective.RISK_ADJUSTED


def test_execute_is_marked_dangerous() -> None:
    request = FinanceCommandRouter().route(
        "execute this trade"
    )

    assert request.intent == Intent.EXECUTE
    assert request.execution_requested is True
    assert request.requires_broker is True


def test_broker_connect() -> None:
    request = FinanceCommandRouter().route(
        "connect my broker"
    )

    assert request.intent == Intent.BROKER_CONNECT
    assert request.requires_broker is True


def test_automation() -> None:
    request = FinanceCommandRouter().route(
        "automate my approved portfolio strategy"
    )

    assert request.intent == Intent.AUTOMATION
    assert request.automation_requested is True
    assert request.requires_broker is True


def test_symbol_extraction() -> None:
    request = FinanceCommandRouter().route(
        "compare AAPL MSFT NVDA"
    )

    assert request.intent == Intent.COMPARE
    assert request.symbols == ("AAPL", "MSFT", "NVDA")


def test_empty_request_is_ambiguous() -> None:
    request = FinanceCommandRouter().route("")

    assert request.domain == Domain.AMBIGUOUS
    
def test_hold_month_is_trade_decision() -> None:
    request = FinanceCommandRouter().route(
        "what should I hold this month?"
    )

    assert request.intent == Intent.TRADE_DECISION
    assert request.horizon == Horizon.MONTH


def test_five_year_consideration_is_long_term_decision() -> None:
    request = FinanceCommandRouter().route(
        "what should I consider for 5 years?"
    )

    assert request.intent == Intent.TRADE_DECISION
    assert request.horizon == Horizon.LONG_TERM