from __future__ import annotations

import os
from dataclasses import replace

from finance_model.inference.provider import GenerationRequest, ModelProvider
from finance_model.ollama_provider import OllamaProvider
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


def build_llm_provider() -> ModelProvider:
    provider = os.getenv("DELTA_LLM_PROVIDER", "ollama").strip().lower()
    if provider != "ollama":
        raise ValueError(
            f"unsupported DELTA_LLM_PROVIDER={provider!r}; "
            "supported provider: ollama"
        )

    return OllamaProvider(
        base_url=os.getenv(
            "DELTA_OLLAMA_URL",
            "http://127.0.0.1:11434",
        ),
        timeout_s=float(
            os.getenv("DELTA_LLM_TIMEOUT", "120")
        ),
    )


class TraderRuntime:
    """Runtime bridge: deterministic quant state + real local LLM synthesis.

    The quantitative/risk engine remains authoritative. The LLM receives the
    computed state as context and generates the user-facing explanation. It
    cannot widen limits, create positions, or submit orders.
    """

    def __init__(
        self,
        *,
        llm_provider: ModelProvider | None = None,
        llm_model: str | None = None,
    ) -> None:
        self._llm = llm_provider or build_llm_provider()
        self._llm_model = llm_model or os.getenv(
            "DELTA_LLM_MODEL",
            "qwen2.5-coder:7b",
        )

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

    def _llm_synthesis(
        self,
        *,
        user_request: FinanceIntent,
        computed_state: str,
    ) -> str:
        prompt = f"""You are DELTA, a finance-specific research assistant.

The deterministic DELTA quantitative/risk engine has already computed the
state below. Treat it as authoritative. Do not invent prices, positions,
returns, news, evidence, or risk metrics. Do not change any risk limit.
Do not claim an order was placed.

USER REQUEST:
{user_request.raw_text}

COMPUTED DELTA STATE:
{computed_state}

Write the response directly for the user. Explain:
1. what the quantitative engine found,
2. why each candidate is trade / wait / no-trade,
3. the main risk and uncertainty,
4. what additional data would change the conclusion.

If the state says no-trade, clearly explain that. Use the supplied numbers
only. Keep the answer concise but useful. Do not mention that you are
following a prompt or that the text is generated.
"""

        result = self._llm.generate(
            GenerationRequest(
                model=self._llm_model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are DELTA. "
                            "Never fabricate financial facts or execution."
                        ),
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    },
                ],
                temperature=0.1,
                max_tokens=1200,
            )
        )

        text = result.text.strip()
        if not text:
            raise RuntimeError("LLM returned an empty response")
        return text

    def _research(self, request: FinanceIntent) -> str:
        mandate = self._mandate(request)
        horizon = _HORIZON_TEXT.get(request.horizon, "week")
        computed = morning_brief(mandate, None, horizon).render()
        return self._llm_synthesis(
            user_request=request,
            computed_state=computed,
        )

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
            try:
                return self._research(request)
            except Exception as exc:
                # Fail closed: if the configured LLM is unavailable, expose
                # the infrastructure failure rather than pretending that an
                # LLM response was produced.
                return (
                    "DELTA LLM ERROR\n"
                    f"{exc}\n"
                    "Start the configured local model provider and retry."
                )

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
                "Risk analysis will not invent positions or P&L."
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
                "execution/risk pipeline after explicit authorization."
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
