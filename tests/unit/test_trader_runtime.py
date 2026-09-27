from __future__ import annotations

from trader.command_router import FinanceCommandRouter
from trader.runtime import TraderRuntime


def test_runtime_executes_trade_decision_path_without_broker() -> None:
    request = FinanceCommandRouter().route("what should I trade this week?")
    response = TraderRuntime().dispatch(request)

    assert "WEEK OPPORTUNITY SCAN" in response
    assert "OPPORTUNITY ANALYSIS" in response
    assert "Nothing will be executed" in response


def test_runtime_never_fabricates_portfolio_state() -> None:
    request = FinanceCommandRouter().route("portfolio risk")
    response = TraderRuntime().dispatch(request)

    assert "No connected portfolio/account state" in response
    assert "will not invent positions" in response


def test_runtime_blocks_direct_execution_at_cli_boundary() -> None:
    request = FinanceCommandRouter().route("execute this trade")
    response = TraderRuntime().dispatch(request)

    assert "SAFETY BOUNDARY" in response
    assert "No live broker adapter" in response
