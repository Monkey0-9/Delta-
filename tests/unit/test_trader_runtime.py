from __future__ import annotations

from finance_model.inference.provider import (
    GenerationRequest,
    GenerationResult,
    ModelProvider,
)
from trader.command_router import FinanceCommandRouter
from trader.runtime import TraderRuntime


class FakeLLM(ModelProvider):
    def __init__(self) -> None:
        self.requests: list[GenerationRequest] = []

    def generate(self, request: GenerationRequest) -> GenerationResult:
        self.requests.append(request)
        return GenerationResult(
            text="LLM GENERATED RESPONSE",
            model=request.model,
            prompt_tokens=10,
            completion_tokens=4,
            latency_ms=1.0,
        )


def test_runtime_uses_real_llm_provider_for_trade_decision(monkeypatch) -> None:
    monkeypatch.setenv("DATA_MODE", "SIMULATION")  # offline-deterministic; live Yahoo unavailable in CI
    llm = FakeLLM()
    request = FinanceCommandRouter().route("what should I trade this week?")

    response = TraderRuntime(
        llm_provider=llm,
        llm_model="test-finance-model",
    ).dispatch(request)

    assert response == "LLM GENERATED RESPONSE"
    assert len(llm.requests) == 1
    assert llm.requests[0].model == "test-finance-model"
    assert "COMPUTED DELTA STATE" in llm.requests[0].messages[1]["content"]
    assert "what should I trade this week?" in llm.requests[0].messages[1]["content"]


def test_runtime_never_fabricates_portfolio_state() -> None:
    llm = FakeLLM()
    request = FinanceCommandRouter().route("portfolio risk")

    response = TraderRuntime(llm_provider=llm).dispatch(request)

    assert "No connected portfolio/account state" in response
    assert "will not invent positions" in response
    assert not llm.requests


def test_runtime_blocks_direct_execution_at_cli_boundary() -> None:
    llm = FakeLLM()
    request = FinanceCommandRouter().route("execute this trade")

    response = TraderRuntime(llm_provider=llm).dispatch(request)

    assert "SAFETY BOUNDARY" in response
    assert "No live broker adapter" in response
    assert not llm.requests
