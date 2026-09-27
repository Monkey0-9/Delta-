from __future__ import annotations

from dataclasses import replace

from trader.intent import FinanceIntent, Horizon, Intent
from trader.mandate import TradingMandate
from trader.mandate_builder import build_mandate
from trader.service import morning_brief


_HORIZON_TEXT = {
    Horizon.TODAY: "today",
    Horizon.INTRADAY: "today",
    Horizon.WEEK: "week",
    Horizon.SHORT_TERM: "week",
    Horizon.MONTH: "month",
    Horizon.MEDIUM_TERM: "month",
    Horizon.YEAR: "year",
    Horizon.LONG_TERM: "year",
    Horizon.UNSPECIFIED: "week",
    Horizon.MIXED: "mixed",
}


class TraderRuntime:
    """Paper-safe runtime binding for the finance terminal.

    This is the bridge between the terminal/router contract and the existing
    mandate -> horizon scan -> ranking -> risk/twin analysis stack.

    It deliberately supports analysis only. Execution, broker mutation and
    autonomous actions remain behind the deterministic authorization boundary.
    """

    def _mandate(self, request: FinanceIntent) -> TradingMandate:
        horizon = _HORIZON_TEXT.get(request.horizon, "week")
        base = build_mandate(
            account_id="CLI-PAPER",
            capital_text="1000000",
            horizon_text=horizon,
            risk_text="moderate",
            universe_text="multi-asset",
            execution_mode="RECOMMENDATION",
        )

        symbols = request.normalized_symbols()
        if symbols:
            base = replace(base, universe=symbols)

        return base

    def dispatch(self, request: FinanceIntent) -> str:
        if request.intent in {
            Intent.TRADE_DECISION,
            Intent.OPPORTUNITIES,
            Intent.OPPORTUNITY_SCAN,
            Intent.ANALYZE_ASSET,
            Intent.ASSET_ANALYSIS,
            Intent.COMPARE,
            Intent.MARKET_ANALYSIS,
            Intent.RESEARCH,
        }:
            mandate = self._mandate(request)
            horizon = _HORIZON_TEXT.get(request.horizon, "week")
            return morning_brief(mandate, None, horizon).render()

        if request.intent in {
            Intent.PORTFOLIO,
            Intent.PORTFOLIO_REVIEW,
            Intent.PORTFOLIO_MANAGEMENT,
            Intent.PORTFOLIO_RISK,
            Intent.STRESS,
        }:
            return (
                "DELTA PORTFOLIO MODE\n"
                "No connected portfolio/account state is available to this "
                "paper CLI session.\n"
                "Risk analysis will not invent positions or P&L. "
                "Connect a supported portfolio source before using "
                "portfolio-specific calculations."
            )

        if request.intent in {
            Intent.EXECUTE,
            Intent.BROKER_CONNECT,
            Intent.BROKER_STATUS,
            Intent.AUTOMATE,
            Intent.AUTOMATION,
            Intent.DAEMON_START,
        }:
            return (
                "DELTA SAFETY BOUNDARY\n"
                "This CLI runtime is analysis-only. No live broker adapter, "
                "autonomous execution authority, or background trading action "
                "is enabled by this path.\n"
                "Paper execution must be entered through the dedicated "
                "execution/risk pipeline after an explicit authorized intent."
            )

        if request.intent in {Intent.STOP, Intent.DAEMON_STOP}:
            return (
                "DELTA: stop request acknowledged at the interface boundary. "
                "No new order was submitted."
            )

        return (
            "DELTA routing is active. "
            f"Intent={request.intent.value} "
            f"Horizon={request.horizon.value}."
        )
