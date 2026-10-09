"""B7a order-path gates — fail-closed kill/firewall/PIT/position/evidence.

Scope: core/canonical_pipeline.py, execution/ems/adapter.py,
execution/live_engine.py. No firewall internals, recon, vault, screens.
"""
from __future__ import annotations

import sys
from decimal import Decimal

import pytest

sys.path.insert(0, ".")


def _pipeline(**kw):
    from core.canonical_pipeline import CanonicalInstitutionalPipeline
    return CanonicalInstitutionalPipeline(initial_cash=1_000_000.0, venue="XNYS", **kw)


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


def _exec_kwargs(mode_name="PAPER", quantity=None, price=None, notional=None):
    from broker.contracts import OrderSide, OrderType
    from trader.mandate import AutonomyMode
    from decimal import Decimal as _D
    return dict(
        mode=getattr(AutonomyMode, mode_name),
        client_order_id="c1", symbol="AAPL", side=OrderSide.BUY,
        quantity=_D("1") if quantity is None else quantity,
        order_type=OrderType.MARKET,
        notional=_D("100") if notional is None else notional,
        price=price,
        market_open=True, data_fresh=True, risk_approved=True,
        authorization_valid=True, kill_switch_active=False,
        model_eligible=True, uncertainty_acceptable=True, duplicate_order=False,
    )


def _bound_evidence(order_id="c1", quantity=None, price=None, notional=None):
    from broker.contracts import OrderSide
    from execution.live_engine import VerifiedRiskEvidence, evidence_order_hash
    from decimal import Decimal as _D
    q = _D("1") if quantity is None else quantity
    n = _D("100") if notional is None else notional
    return VerifiedRiskEvidence(
        risk_verdict="approve",
        order_id=order_id,
        order_hash=evidence_order_hash(
            client_order_id="c1", symbol="AAPL",
            quantity=q, side=OrderSide.BUY, price=price, notional=n),
    )


# 1. kill-active execute_order refused -------------------------------------
def test_kill_active_execute_order_refused():
    from core.canonical_pipeline import CanonicalOrderStatus, OrderSide
    pipe = _pipeline()
    order = pipe.create_order("SPY", OrderSide.BUY, 10, 500.0)
    assert order.status == CanonicalOrderStatus.SUBMITTED
    pipe.kill_switch_halted = True  # halt AFTER submit, before execution
    fill = pipe.execute_order(order, market_price=500.0)
    assert fill is None
    assert pipe.orders[order.order_id].status == CanonicalOrderStatus.REJECTED
    reasons = " ".join(
        str(e.details.get("reason", "")) for e in pipe.audit_log
        if e.stage in ("ORDER_BLOCKED", "ORDER_REJECTED"))
    assert "kill" in reasons.lower()


def test_kill_board_execute_order_refused():
    from core.canonical_pipeline import CanonicalOrderStatus, OrderSide
    from risk.kill_switch.kill_switch import KillSwitchBoard
    board = KillSwitchBoard()
    pipe = _pipeline(kill_board=board)
    order = pipe.create_order("SPY", OrderSide.BUY, 10, 500.0)
    assert order.status == CanonicalOrderStatus.SUBMITTED
    board.glob.activate(actor="b7a-test")
    fill = pipe.execute_order(order, market_price=500.0)
    assert fill is None
    assert pipe.orders[order.order_id].status == CanonicalOrderStatus.REJECTED


# 2. firewall-block refused --------------------------------------------------
def test_firewall_block_refused_at_execution():
    from core.canonical_pipeline import CanonicalOrderStatus, OrderSide
    from risk.firewall.firewall import RiskFirewall
    from risk.kill_switch.kill_switch import KillSwitchBoard
    board = KillSwitchBoard()
    pipe = _pipeline(firewall=RiskFirewall(kill_switch=board))  # injected
    order = pipe.create_order("SPY", OrderSide.BUY, 10, 500.0)
    assert order.status == CanonicalOrderStatus.SUBMITTED  # board quiet
    board.glob.activate(actor="b7a-test")  # trip AFTER submit, before execution
    fill = pipe.execute_order(order, market_price=500.0)
    assert fill is None
    assert pipe.orders[order.order_id].status == CanonicalOrderStatus.REJECTED
    reasons = " ".join(
        str(e.details.get("reason", "")) for e in pipe.audit_log
        if e.stage in ("ORDER_BLOCKED", "ORDER_REJECTED"))
    assert "firewall" in reasons.lower()


# 3. PIT-gated synthetic refused on PAPER decision path ----------------------
def test_pit_gated_synthetic_refused_on_paper_path():
    pipe = _pipeline(decision_path="PAPER")
    result = pipe.run_cycle(symbols=("SPY",))
    assert result["executed_fills"] == []
    assert result["blocked_reason"] is not None
    assert any(k in result["blocked_reason"].lower()
               for k in ("synthetic", "pit", "hash_seeded"))


# 4. naked SELL refused -------------------------------------------------------
def test_naked_sell_refused():
    from core.canonical_pipeline import CanonicalOrderStatus, OrderSide
    pipe = _pipeline()
    order = pipe.create_order("SPY", OrderSide.SELL, 10, 500.0)
    assert order.status == CanonicalOrderStatus.REJECTED
    reasons = " ".join(
        str(e.details.get("reason", "")) for e in pipe.audit_log
        if e.stage in ("ORDER_BLOCKED", "ORDER_REJECTED"))
    assert "position" in reasons.lower()
    # Covered SELL works: buy first, then sell partial.
    buy = pipe.create_order("SPY", OrderSide.BUY, 10, 500.0)
    assert buy.status == CanonicalOrderStatus.SUBMITTED
    assert pipe.execute_order(buy, market_price=500.0) is not None
    sell = pipe.create_order("SPY", OrderSide.SELL, 5, 500.0)
    assert sell.status == CanonicalOrderStatus.SUBMITTED
    # Explicit short-enable flag permits naked SELL.
    short_pipe = _pipeline(allow_short=True)
    naked = short_pipe.create_order("SPY", OrderSide.SELL, 10, 500.0)
    assert naked.status == CanonicalOrderStatus.SUBMITTED


# 5. EMS bypass refused-or-routed ----------------------------------------------
def test_ems_bypass_refused_without_gateway():
    from execution.ems.adapter import BrokerError, EMS, ExecutionRequest

    class _Venue:
        def __init__(self):
            self.calls = []

        def submit(self, request):
            self.calls.append(request)
            from execution.ems.adapter import ExecutionAck
            return ExecutionAck(request.order_id, True, "V-" + request.order_id, "filled")

    venue = _Venue()
    ems = EMS(venue)
    with pytest.raises(BrokerError, match="OrderGateway"):
        ems.submit(ExecutionRequest("bypass-1", "SPY", 10.0))
    assert venue.calls == []  # never silently filled


def test_ems_routed_via_firewall_with_audit():
    from execution.ems.adapter import EMS, ExecutionRequest
    from execution.paper.broker import PaperBroker
    from risk.firewall.firewall import RiskFirewall

    fw = RiskFirewall()
    paper = PaperBroker({"SPY": 100.0})
    ems = EMS(paper, firewall=fw)
    ack = ems.submit(ExecutionRequest("routed-1", "SPY", 10.0))
    assert ack.accepted
    assert "routed-1" in paper.orders
    assert "routed-1" in fw._seen_keys  # firewall saw it
    assert len(ems.audit_log) >= 1  # audit saw it


def test_ems_firewall_kill_blocks_venue():
    from execution.ems.adapter import EMS, ExecutionRequest
    from execution.paper.broker import PaperBroker
    from risk.firewall.firewall import RiskFirewall
    from risk.kill_switch.kill_switch import KillSwitchBoard

    board = KillSwitchBoard()
    board.glob.activate(actor="b7a-test")
    fw = RiskFirewall(kill_switch=board)
    paper = PaperBroker({"SPY": 100.0})
    ems = EMS(paper, firewall=fw)
    ack = ems.submit(ExecutionRequest("kill-1", "SPY", 10.0))
    assert not ack.accepted
    assert "kill" in ack.message.lower()
    assert "kill-1" not in paper.orders  # venue never touched


# 6. PAPER without evidence refused ---------------------------------------------
def test_paper_without_evidence_refused():
    from execution.live_engine import LiveExecutionEngine
    eng = LiveExecutionEngine(broker=_FakeBroker(), mandate=_paper_mandate())
    res = eng.execute(**_exec_kwargs("PAPER"))
    assert not res.allowed
    assert "risk_evidence_missing" in res.reasons
    assert eng.broker.submitted == []


# 7. verdict bound to wrong order refused ----------------------------------------
def test_verdict_bound_to_wrong_order_refused():
    from execution.live_engine import LiveExecutionEngine
    eng = LiveExecutionEngine(broker=_FakeBroker(), mandate=_paper_mandate())
    bad = _bound_evidence(order_id="some-other-order")
    res = eng.execute(**_exec_kwargs("PAPER"), risk_evidence=bad)
    assert not res.allowed
    assert any("evidence" in r for r in res.reasons)
    assert any("order" in r or "mismatch" in r for r in res.reasons)
    assert eng.broker.submitted == []
    # Positive control: correctly bound evidence on PAPER is allowed.
    eng2 = LiveExecutionEngine(broker=_FakeBroker(), mandate=_paper_mandate())
    res2 = eng2.execute(**_exec_kwargs("PAPER"), risk_evidence=_bound_evidence("c1"))
    assert res2.allowed, res2.reasons


# FIX 1. risk-evaluation error blocks (fail-closed) -----------------------------
def test_risk_evaluation_error_blocks():
    from core.canonical_pipeline import OrderSide
    pipe = _pipeline()

    def _boom(prices):
        raise RuntimeError("risk store down")

    pipe.evaluate_risk = _boom  # type: ignore[method-assign]
    ok, reason = pipe.pre_trade_check("SPY", OrderSide.BUY, 10, 500.0)
    assert not ok
    assert "risk evaluation error fail-closed" in reason


# FIX 2. unrecognized kill-board shape blocks (fail-closed) ----------------------
def test_unknown_kill_board_shape_blocks():
    from core.canonical_pipeline import OrderSide
    pipe = _pipeline(kill_board=object())  # bound but no known probe
    ok, reason = pipe.pre_trade_check("SPY", OrderSide.BUY, 10, 500.0)
    assert not ok
    assert "unrecognized" in reason.lower()


def test_non_callable_truthy_any_active_blocks():
    from types import SimpleNamespace
    from core.canonical_pipeline import OrderSide
    pipe = _pipeline(kill_board=SimpleNamespace(any_active=True))
    ok, reason = pipe.pre_trade_check("SPY", OrderSide.BUY, 10, 500.0)
    assert not ok
    assert "kill" in reason.lower()
    # Falsy flag form is recognized as quiet: the check proceeds.
    quiet = _pipeline(kill_board=SimpleNamespace(any_active=False))
    ok2, _ = quiet.pre_trade_check("SPY", OrderSide.BUY, 10, 500.0)
    assert ok2


# FIX 3. pre-checks do not pollute the firewall idempotency set ------------------
def test_pre_trade_probe_does_not_reserve_firewall_keys():
    from core.canonical_pipeline import OrderSide
    from risk.firewall.firewall import RiskFirewall
    fw = RiskFirewall()
    pipe = _pipeline(firewall=fw)
    before = set(fw._seen_keys)
    ok, reason = pipe.pre_trade_check("SPY", OrderSide.BUY, 10, 500.0)
    assert ok, reason
    assert set(fw._seen_keys) == before  # probe rolled back, nothing burned


# FIX 4. venue-raises-once → retry same order_id succeeds -------------------------
def test_ems_retry_after_venue_error_succeeds():
    from execution.ems.adapter import EMS, ExecutionAck, ExecutionRequest
    from risk.firewall.firewall import RiskFirewall

    class _FlakyVenue:
        def __init__(self):
            self.calls = 0

        def submit(self, request):
            self.calls += 1
            if self.calls == 1:
                raise ConnectionError("venue timeout")
            return ExecutionAck(request.order_id, True, "V-" + request.order_id, "filled")

    fw = RiskFirewall()
    ems = EMS(_FlakyVenue(), firewall=fw)
    first = ems.submit(ExecutionRequest("retry-1", "SPY", 10.0))
    assert not first.accepted
    assert "retryable" in first.message.lower()
    assert "retry-1" not in fw._seen_keys  # key released, not burned
    second = ems.submit(ExecutionRequest("retry-1", "SPY", 10.0))
    assert second.accepted  # same order_id admitted on retry


# FIX 5a. mutated economics with the same order id refused --------------------------
def test_mutated_economics_same_id_refused():
    from execution.live_engine import LiveExecutionEngine
    eng = LiveExecutionEngine(broker=_FakeBroker(), mandate=_paper_mandate())
    ev = _bound_evidence("c1")  # minted for quantity 1, notional 100
    res = eng.execute(
        **_exec_kwargs("PAPER", quantity=Decimal("2"), notional=Decimal("200")),
        risk_evidence=ev,
    )
    assert not res.allowed
    assert any("mismatch" in r or "bound" in r for r in res.reasons)
    assert eng.broker.submitted == []


def test_price_change_refused():
    from execution.live_engine import LiveExecutionEngine
    eng = LiveExecutionEngine(broker=_FakeBroker(), mandate=_paper_mandate())
    ev = _bound_evidence("c1", price=Decimal("100"))
    res = eng.execute(
        **_exec_kwargs("PAPER", price=Decimal("101")), risk_evidence=ev)
    assert not res.allowed
    assert any("mismatch" in r or "bound" in r for r in res.reasons)
    assert eng.broker.submitted == []
    # Positive control: identical price verifies.
    eng2 = LiveExecutionEngine(broker=_FakeBroker(), mandate=_paper_mandate())
    res2 = eng2.execute(
        **_exec_kwargs("PAPER", price=Decimal("100")),
        risk_evidence=_bound_evidence("c1", price=Decimal("100")),
    )
    assert res2.allowed, res2.reasons


# FIX 5b. Decimal formatting stability -----------------------------------------------
def test_evidence_hash_decimal_stability():
    from broker.contracts import OrderSide
    from execution.live_engine import LiveExecutionEngine, evidence_order_hash
    h1 = evidence_order_hash(
        client_order_id="c1", symbol="AAPL",
        quantity=Decimal("1"), side=OrderSide.BUY, notional=Decimal("100"))
    h2 = evidence_order_hash(
        client_order_id="c1", symbol="AAPL",
        quantity=Decimal("1.0"), side=OrderSide.BUY, notional=Decimal("100.00"))
    assert h1 == h2
    assert len(h1) == 64  # full SHA-256 digest, not truncated
    # End-to-end: evidence minted as 1.0 verifies execution as 1.
    from execution.live_engine import VerifiedRiskEvidence
    eng = LiveExecutionEngine(broker=_FakeBroker(), mandate=_paper_mandate())
    res = eng.execute(
        **_exec_kwargs("PAPER"),
        risk_evidence=VerifiedRiskEvidence(
            risk_verdict="approve", order_id="c1", order_hash=h2),
    )
    assert res.allowed, res.reasons
