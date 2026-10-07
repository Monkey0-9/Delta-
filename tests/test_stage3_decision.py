"""Stage-3 Research→Decision tests: NO_TRADE, risk veto, tool gateway, journal, hard constraints."""
from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest


def _di(**kw):
    from decision.engine import DecisionEngine, DecisionInput
    from decision.horizon import DecisionHorizon
    base = dict(instrument_id=uuid4(), horizon=DecisionHorizon.INTRADAY,
                expected_return=Decimal("0.05"), confidence=Decimal("0.8"),
                risk_penalty=Decimal("0.01"), transaction_cost=Decimal("0.005"),
                utility_threshold=Decimal("0.0"))
    base.update(kw)
    return DecisionInput(**base), DecisionEngine()


def test_no_trade_on_risk_and_policy_block():
    from decision.decision import DecisionAction
    di, eng = _di(risk_blocked=True, block_reason="KILL_ACTIVE")
    assert eng.evaluate(di).action == DecisionAction.NO_TRADE
    di2, _ = _di(policy_blocked=True, block_reason="REGIME_HALT")
    assert eng.evaluate(di2).action == DecisionAction.NO_TRADE


def test_wait_vs_buy_semantics():
    from decision.decision import DecisionAction
    di, eng = _di(confidence=Decimal("0.3"))
    assert eng.evaluate(di).action == DecisionAction.WAIT
    di2, _ = _di()
    assert eng.evaluate(di2).action == DecisionAction.BUY


def test_risk_veto_overrides_ml_approve():
    # model recommends BUY, firewall vetoes → NO_TRADE (never inverse)
    from decision.decision import DecisionAction
    di, eng = _di(expected_return=Decimal("0.20"), confidence=Decimal("0.95"),
                  risk_blocked=True, block_reason="VAR_BREACH")
    assert eng.evaluate(di).action == DecisionAction.NO_TRADE


def test_tool_gateway_approval_audit_idempotency():
    from finance_model.tools.contracts import ToolRequest
    from finance_model.tools.gateway import DuplicateRequest, ToolApprovalRequired, ToolGateway
    from finance_model.tools.registry import FinanceToolRegistry, ToolDefinition
    reg = FinanceToolRegistry()
    reg.register(ToolDefinition(name="market_data", description="md", risk="read_only",
                                handler=lambda symbol: {"px": 100.0, "symbol": symbol}))
    reg.register(ToolDefinition(name="broker_place", description="x", risk="sensitive",
                                handler=lambda: {}))
    gw = ToolGateway(registry=reg)
    r1 = gw.call(ToolRequest(tool_name="market_data", arguments={"symbol": "AAPL"},
                             request_id="r-1"))
    assert r1.success and r1.data["px"] == 100.0
    with pytest.raises(DuplicateRequest):
        gw.call(ToolRequest(tool_name="market_data", arguments={"symbol": "AAPL"},
                            request_id="r-1"))
    with pytest.raises(KeyError):
        gw.call(ToolRequest(tool_name="nope", arguments={}, request_id="r-2"))
    with pytest.raises(ToolApprovalRequired):
        gw.call(ToolRequest(tool_name="broker_place", arguments={}, request_id="r-3"))
    gw.approve("r-3")
    assert gw.call(ToolRequest(tool_name="broker_place", arguments={},
                               request_id="r-3")).success
    assert len(gw.audit) >= 3


def test_oms_journal_replay_after_kill():
    import tempfile
    from pathlib import Path
    from core.oms.journal import OmsJournal
    with tempfile.TemporaryDirectory() as td:
        jp = Path(td) / "oms.jsonl"
        j = OmsJournal(jp)
        j.append("O-1", "CREATED"); j.append("O-1", "VALIDATED")
        j.append("O-1", "RISK_APPROVED"); j.append("O-1", "SUBMITTED")
        # kill-9: new handle replays
        j2 = OmsJournal(jp)
        assert j2.snapshot() == {"O-1": "SUBMITTED"}
        j2.append("O-1", "ACKNOWLEDGED"); j2.append("O-1", "FILLED")
        assert j2.snapshot()["O-1"] == "FILLED"
        with pytest.raises(ValueError):
            j2.append("O-1", "SUBMITTED")  # terminal + illegal
        with pytest.raises(ValueError):
            j2.append("O-9", "FILLED")  # must start CREATED


def test_hard_constraints_block_with_reasons_and_determinism():
    from quant.portfolio.hard import enforce_hard_constraints
    ok, reasons = enforce_hard_constraints({"A": 0.3, "B": 0.3})
    assert ok and reasons == []
    ok2, r2 = enforce_hard_constraints({"A": 0.9, "B": 0.2})
    assert not ok2 and any("max_single" in r or "gross" in r for r in r2)
    ok3, r3 = enforce_hard_constraints({"A": 0.5, "B": -0.1})
    assert not ok3 and any("long-only" in r for r in r3)
    assert enforce_hard_constraints({"A": 0.3, "B": 0.3}) == (True, [])
