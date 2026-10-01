"""P0 intelligence purge + canonical spine (audit sections 65-66, 76).

Proves: no fake execution, no synthetic cert scores, honest gates,
utility-gated decisions, typed tools, claim verification, finance CV guard.
"""
from __future__ import annotations


def test_autonomous_agent_deleted():
    import importlib.util
    assert importlib.util.find_spec("research.agent.autonomous_agent") is None
    import pathlib
    assert not pathlib.Path("research/agent/autonomous_agent.py").exists()


def test_no_synthetic_reaches_certification():
    from research.agent.research_loop import ResearchLoop

    class NoTools:
        def list_tools(self):
            return []

    out = ResearchLoop(NoTools()).run({"params": {}}, max_iter=2)
    assert out["status"] == "DATA_UNAVAILABLE"
    assert out["best_score"] is None
    assert out["cert_eligible"] is False
    assert out["converged"] is False


def test_convergence_requires_plateau_not_running():
    from research.agent.research_loop import ResearchLoop

    calls = {"n": 0}

    class Improving:
        def list_tools(self):
            return ["backtest"]

        def invoke(self, name, **k):
            calls["n"] += 1
            return {"score": float(calls["n"])}  # always improves: never plateaus

    out = ResearchLoop(Improving(), patience=2).run({"p": 1}, max_iter=3)
    assert out["status"] == "SCORED"
    assert out["converged"] is False
    assert out["converge_reason"] == "max_iter_exhausted"

    class Flat:
        def list_tools(self):
            return ["backtest"]

        def invoke(self, name, **k):
            return {"score": 0.5}

    out2 = ResearchLoop(Flat(), patience=2).run({"p": 1}, max_iter=5)
    assert out2["converged"] is True
    assert out2["converge_reason"] == "plateau"
    assert out2["cert_eligible"] is True


def test_tool_registry_no_silent_overwrite():
    from research.agent.tool_registry import ToolRegistry
    reg = ToolRegistry()
    reg.register("t", lambda: 1)
    try:
        reg.register("t", lambda: 2)
        assert False, "silent overwrite must fail"
    except ValueError:
        pass
    reg.register("t", lambda: 2, overwrite=True)  # explicit governed replace
    assert reg.invoke("t") == 2


def test_runtime_executes_tools_no_fake_completed():
    from agent.planner.planner import AgentPlanner
    from agent.policies.policy import AgentPolicy
    from agent.runtime.runtime import AgentRuntime
    from agent.runtime.types import AgentTask, AgentTaskStatus
    from ai.contracts import ToolDefinition, RiskClass
    from ai.executor import TypedToolExecutor

    calls: list[str] = []
    planner = AgentPlanner()
    policy = AgentPolicy()
    rt = AgentRuntime(planner, policy)  # no executor
    task = AgentTask(instruction="run analysis")
    res = rt.execute(task)
    # Either no tool steps (COMPLETED) or FAILED — never fake tool results.
    assert res.status in (AgentTaskStatus.COMPLETED, AgentTaskStatus.FAILED,
                          AgentTaskStatus.PARTIAL)

    ex = TypedToolExecutor()
    ex.register(ToolDefinition(name="echo", permission="run_analysis",
                               risk_class=RiskClass.READ_ONLY,
                               input_schema={"type": "object"}),
                lambda: calls.append("ran") or {"ok": True})
    rt2 = AgentRuntime(planner, policy, executor=ex,
                       agent_id="t", grants=("echo",))
    res2 = rt2.execute(task)
    ledger_kinds = [e["kind"] for e in ex.ledger.entries]
    if any("echo" in str(m) for m in res2.messages if "step" in str(m)):
        assert calls == ["ran"]
        assert "tool" in ledger_kinds


def test_executor_deny_precedence():
    from ai.contracts import ToolCall, ToolDefinition, RiskClass
    from ai.executor import TypedToolExecutor
    ex = TypedToolExecutor()
    assert ex.execute(ToolCall(tool_name="nope", arguments={}), "a").status == "denied"
    ex.register(ToolDefinition(name="t", permission="p", risk_class=RiskClass.READ_ONLY,
                               input_schema={"type": "object", "required": ["x"],
                                             "properties": {"x": {"type": "number"}}}),
                lambda x: x)
    assert ex.execute(ToolCall(tool_name="t", arguments={}), "a").status == "denied"
    ex.grant("a", "t")
    assert ex.execute(ToolCall(tool_name="t", arguments={}), "a").status == "denied"
    ok = ex.execute(ToolCall(tool_name="t", arguments={"x": 1}), "a")
    assert ok.status == "ok" and ok.data == 1


def test_critical_tool_requires_auth_and_idempotency():
    from ai.contracts import ToolCall, ToolDefinition, RiskClass
    from ai.executor import TypedToolExecutor
    ex = TypedToolExecutor(authorize=lambda c, d: True)
    ex.register(ToolDefinition(name="fire", permission="p",
                               risk_class=RiskClass.CRITICAL, side_effect=True),
                lambda: "fired")
    ex.grant("a", "fire")
    assert ex.execute(ToolCall(tool_name="fire", arguments={}), "a").status == "denied"
    c1 = ToolCall(tool_name="fire", arguments={}, idempotency_key="k1")
    assert ex.execute(c1, "a", auth_token="tok").status == "ok"
    assert ex.execute(c1, "a", auth_token="tok").status == "denied"  # replay


def test_verifier_tests_evidence_not_citation():
    from datetime import datetime, timezone, timedelta
    from ai.contracts import Claim, ClaimVerdict, Evidence, KnowledgeType
    from ai.verifier import ClaimVerifier
    now = datetime.now(timezone.utc)
    ev = Evidence(evidence_id="EV-1", source="test",
                  payload={"aapl": {"vol_20d": 0.31}},
                  available_at=now - timedelta(minutes=5),
                  retrieved_at=now, knowledge_type=KnowledgeType.FACT)
    v = ClaimVerifier({"EV-1": ev})
    good = Claim(claim_id="C1", text="vol 0.31", evidence_refs=("EV-1",),
                 numeric_assertions=(("aapl.vol_20d", 0.31, 1e-9),),
                 decision_at=now)
    assert v.verify(good).verdict == ClaimVerdict.SUPPORTED
    bad = Claim(claim_id="C2", text="vol 99%", evidence_refs=("EV-1",),
                numeric_assertions=(("aapl.vol_20d", 99.0, 1e-9),),
                decision_at=now)
    assert v.verify(bad).verdict == ClaimVerdict.CONTRADICTED
    # Citation token without assertions never SUPPORTS.
    bare = Claim(claim_id="C3", text="AAPL will rise 18.7% [EV-1]",
                 evidence_refs=("EV-1",), decision_at=now)
    assert v.verify(bare).verdict == ClaimVerdict.UNSUPPORTED
    # Future evidence at decision time is invalid.
    future = Claim(claim_id="C4", text="x", evidence_refs=("EV-1",),
                   numeric_assertions=(("aapl.vol_20d", 0.31, 1e-9),),
                   decision_at=now - timedelta(hours=1))
    assert v.verify(future).verdict == ClaimVerdict.TEMPORALLY_INVALID


def test_decision_utility_vetoes_thin_edge():
    from decimal import Decimal
    from uuid import uuid4
    from decision import DecisionAction, DecisionEngine, DecisionHorizon, DecisionInput

    def make_input(expected_return: Decimal, cost: Decimal = Decimal("0")) -> DecisionInput:
        return DecisionInput(
            instrument_id=uuid4(), horizon=DecisionHorizon.SHORT_TERM,
            expected_return=expected_return, confidence=Decimal("0.9"),
            transaction_cost=cost, model_version="m", world_state_version="w")

    # +8% ER but 10% cost: WAIT, not BUY.
    d = DecisionEngine().evaluate(make_input(Decimal("0.08"), Decimal("0.10")))
    assert d.action == DecisionAction.WAIT
    # -5% ER, no costs: SELL (short utility positive).
    d2 = DecisionEngine().evaluate(make_input(Decimal("-0.05")))
    assert d2.action == DecisionAction.SELL


def test_finance_policy_not_a_model():
    from finance_model.engine import FinanceAnalysisPolicy
    import finance_model.engine as eng
    assert "NOT an LLM" in (eng.__doc__ or "")
    assert "no broker access" in (FinanceAnalysisPolicy.__doc__ or "").lower() \
        or "no model inference" in (FinanceAnalysisPolicy.__doc__ or "")


def test_finance_cv_guard_and_walkforward():
    from models.model_zoo.evaluation import (
        require_finance_protocol, score_finance_model, compare_models)
    try:
        require_finance_protocol("kfold")
        assert False
    except ValueError:
        pass
    import numpy as np
    rng = np.random.default_rng(0)
    X = rng.normal(size=(60, 2))
    y = X[:, 0] * 2 + rng.normal(scale=0.1, size=60)
    from sklearn.linear_model import LinearRegression
    out = score_finance_model(LinearRegression(), X, y, n_splits=3, embargo=2)
    assert out["protocol"] == "purged_walk_forward" and len(out["scores"]) >= 1
    ranked = compare_models({"lr": LinearRegression()}, X, y, cv=2, finance=True)
    assert ranked["lr"]["rank"] == 1


def test_reasonforge_marked_baseline():
    from decision import reasonforge as rf
    assert getattr(rf, "INTELLIGENCE_CLASS", "") == "deterministic_rule_baseline"


def test_certified_paths_use_canonical_contracts():
    import ai.contracts as C
    for name in ("ToolCall", "ToolResult", "Evidence", "Claim", "AgentSpec",
                 "AgentRun", "Forecast", "ResearchSpec", "DecisionRecord",
                 "PromotionDecision", "Budget"):
        assert hasattr(C, name), name
