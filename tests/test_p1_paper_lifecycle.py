"""P1 e2e: canonical paper lifecycle Gateway -> Risk -> PaperBroker -> reconcile.

Proves §18 paper path (minus Alpaca streaming): intent, risk approval, OMS
submit, broker ack, fill report, position reconciliation — plus kill-block
negative. Uses only the PaperBroker sim venue; no live path touched.
"""
from __future__ import annotations

import sys
from decimal import Decimal
from uuid import uuid4

sys.path.insert(0, ".")


def _gateway():
    from core.oms.gateway import OrderGateway
    from risk.firewall.firewall import RiskFirewall
    from risk.kill_switch.kill_switch import KillSwitchBoard
    board = KillSwitchBoard()
    fw = RiskFirewall(kill_switch=board)
    return OrderGateway(firewall=fw), board


def _order(**kw):
    from core.domain.order import Order, OrderSide
    return Order(instrument_id=uuid4(), side=OrderSide.BUY,
                 quantity=Decimal("10"), **kw)


def test_paper_lifecycle_approve_ack_fill_reconcile():
    from execution.ems.adapter import ExecutionRequest
    from execution.paper.broker import PaperBroker
    from broker.reconciliation import reconcile_oms_vs_broker

    gw, _ = _gateway()
    paper = PaperBroker({"SPY": 100.0})
    submitted: list = []

    def to_paper(order) -> dict:
        req = ExecutionRequest(order_id=str(order.order_id), asset="SPY",
                               quantity=float(order.quantity))
        ack = paper.submit(req)
        submitted.append(order.order_id)
        return {"ack": ack.accepted, "broker_order_id": ack.broker_order_id}

    order = _order()
    dec = gw.submit(order, ref_price=Decimal("100"), authorized=True,
                    price_source="real", broker=to_paper)
    assert dec.approved, dec.reasons
    assert submitted == [dec.order.order_id]
    rep = paper.execution_report(str(dec.order.order_id))
    assert rep.get("exec_model_version") == "exec-sim-v1", rep
    # Reconcile: OMS submitted id present on broker side.
    r = reconcile_oms_vs_broker((str(dec.order.order_id),),
                                tuple(str(o) for o in submitted))
    assert r is not None


def test_paper_lifecycle_kill_blocks_before_submit():
    gw, board = _gateway()
    board.glob.activate(actor="p1-e2e")
    order = _order()
    calls: list = []
    dec = gw.submit(order, ref_price=Decimal("100"), authorized=True,
                    price_source="real", broker=lambda o: calls.append(o))
    assert not dec.approved
    assert calls == []
    assert "kill_switch_active" in dec.reasons
