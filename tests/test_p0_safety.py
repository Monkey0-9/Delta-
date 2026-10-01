"""P0 safety tests — fail-closed guarantees added 2026-09-30.

Covers §54.E evidence for today's build:
- audit ledger survives reload (hash preserved)
- walk-forward defaults purge/embargo=1
- live engine blocks spoofed bools without evidence
- kill board + breaker halt wiring
- research loop strict vs synthetic labeling
"""
from __future__ import annotations

import json
import sys
import tempfile
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, ".")


def test_audit_survives_reload():
    from core.audit import AuditLedger
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "audit.log"
        led = AuditLedger(audit_log_path=p)
        h = led.add_entry("order", {"id": "1"})
        assert led.verify_chain()
        # Reload from disk — history must NOT be dropped (P0 bug was drop-all).
        led2 = AuditLedger(audit_log_path=p)
        assert len(led2.get_entries()) == 1
        assert led2.verify_chain()
        assert led2.get_entry_by_hash(h) is not None


def test_walkforward_fail_closed_defaults():
    from validation.walk_forward.splitter import walk_forward_splits
    splits = walk_forward_splits(100, train=50, test=10, step=10)
    assert splits, "need at least one split"
    for s in splits:
        assert s.train_end + 2 == s.test_start  # purge=1 + embargo=1
    # Explicit legacy opt-out still possible for non-temporal unit tests.
    legacy = walk_forward_splits(100, train=50, test=10, step=10, purge=0, embargo=0)
    assert legacy[0].train_end == legacy[0].test_start


def _paper_mandate():
    from trader.mandate import AutonomyMode, TradingMandate
    return TradingMandate(
        account_id="test",
        universe=("AAPL",),
        allowed_modes=frozenset({AutonomyMode.PAPER, AutonomyMode.AUTONOMOUS}),
        max_position_notional=Decimal("100000"),
        max_order_notional=Decimal("10000"),
        max_daily_turnover=Decimal("50000"),
    )


class _FakeBroker:
    def __init__(self, healthy=True):
        self._healthy = healthy
        self.submitted = []

    def health(self):
        return self._healthy

    def submit(self, order):
        self.submitted.append(order)
        from broker.contracts import BrokerOrderResult
        return BrokerOrderResult(broker_order_id="b1", client_order_id=order.client_order_id,
                                 status="ok", raw={})


def _exec_kwargs(mode_name="AUTONOMOUS"):
    from broker.contracts import OrderSide, OrderType
    from trader.mandate import AutonomyMode
    return dict(
        mode=getattr(AutonomyMode, mode_name),
        client_order_id="c1", symbol="AAPL", side=OrderSide.BUY,
        quantity=Decimal("1"), order_type=OrderType.MARKET, notional=Decimal("100"),
        market_open=True, data_fresh=True, risk_approved=True,
        authorization_valid=True, kill_switch_active=False,
        model_eligible=True, uncertainty_acceptable=True, duplicate_order=False,
    )


def test_live_engine_blocks_spoofed_bools_without_evidence():
    from execution.live_engine import LiveExecutionEngine
    eng = LiveExecutionEngine(broker=_FakeBroker(), mandate=_paper_mandate())
    res = eng.execute(**_exec_kwargs("AUTONOMOUS"))
    assert not res.allowed and "risk_evidence_missing" in res.reasons
    assert eng.broker.submitted == []


def test_live_engine_paper_legacy_still_works():
    from execution.live_engine import LiveExecutionEngine
    eng = LiveExecutionEngine(broker=_FakeBroker(), mandate=_paper_mandate())
    res = eng.execute(**_exec_kwargs("PAPER"))
    assert res.allowed


def test_live_engine_evidence_mismatch_blocks():
    from execution.live_engine import LiveExecutionEngine, VerifiedRiskEvidence
    from risk.kill_switch.kill_switch import KillSwitchBoard
    eng = LiveExecutionEngine(broker=_FakeBroker(), mandate=_paper_mandate())
    board = KillSwitchBoard()
    # Caller claims risk_approved=True but evidence says block.
    res = eng.execute(**_exec_kwargs("AUTONOMOUS"),
                      risk_evidence=VerifiedRiskEvidence(risk_verdict="block"),
                      kill_board=board)
    assert not res.allowed and "risk_evidence_mismatch" in res.reasons
    # Kill board active but bool claims inactive -> mismatch block.
    board.glob.activate(actor="test")
    res2 = eng.execute(**_exec_kwargs("AUTONOMOUS"),
                       risk_evidence=VerifiedRiskEvidence(risk_verdict="approve"),
                       kill_board=board)
    assert not res2.allowed


def test_kill_board_any_active_blocks_firewall():
    from risk.firewall.firewall import RiskFirewall
    from risk.kill_switch.kill_switch import KillSwitchBoard
    from risk.pre_trade.validation import TradeIntent
    board = KillSwitchBoard()
    fw = RiskFirewall(kill_switch=board)
    board.strategy.activate(actor="test")
    d = fw.check(TradeIntent(uuid4(), uuid4(), "buy", Decimal("1"), None, "k-1", True))
    assert d.verdict.value == "block"
    assert "kill_switch_active" in d.reasons


def test_breaker_runs_halt_and_binds_board():
    from risk.emergency.breaker import CircuitBreaker
    from risk.kill_switch.kill_switch import KillSwitchBoard
    board = KillSwitchBoard()
    br = CircuitBreaker()
    called = []
    br.register_halt_callback(lambda: called.append(1))
    br.bind_to_kill_board(board)
    br.trigger("test halt")
    assert called == [1]
    assert board.any_active()


def test_research_loop_strict_and_labeling():
    from research.agent.research_loop import ResearchLoop

    class Exploding:
        def list_tools(self):
            return ["backtest"]

        def invoke(self, *a, **k):
            raise RuntimeError("boom")

    strict = ResearchLoop(Exploding(), strict=True)
    try:
        strict.run({"params": {}}, max_iter=1)
        assert False, "strict must raise"
    except RuntimeError:
        pass
    loose = ResearchLoop(Exploding(), strict=False)
    out = loose.run({"params": {}}, max_iter=1)
    assert out["status"] == "DATA_UNAVAILABLE"
    assert out["synthetic_used"] is False
    assert out["cert_eligible"] is False
    demo = ResearchLoop(Exploding(), strict=False, allow_synthetic=True)
    dout = demo.run({"params": {}}, max_iter=1)
    assert dout["status"] == "SYNTHETIC_DEMO"
    assert dout["synthetic_used"] is True
    assert dout["cert_eligible"] is False
