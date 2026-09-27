"""P3: execution planner + live-broker guard + reconciliation."""
from __future__ import annotations

from decimal import Decimal

import pytest

from broker.live_base import create_live_broker, live_enabled
from broker.reconciliation import reconcile_oms_vs_broker
from execution.planner import plan_execution, select_algo


def test_planner_children_sum_exactly():
    plan = plan_execution(quantity=Decimal("300"), adv=Decimal("10000"))
    assert plan.algo == "VWAP"
    assert sum((c.quantity for c in plan.children), Decimal("0")) == Decimal("300")


def test_planner_branches():
    assert select_algo(participation=0.001, spread_bps=5, urgency="normal")[0] == "PASSIVE"
    assert select_algo(participation=0.20, spread_bps=5, urgency="normal")[0] == "POV"
    assert select_algo(participation=0.20, spread_bps=5, urgency="high")[0] == "AGGRESSIVE"
    assert select_algo(participation=0.001, spread_bps=80, urgency="normal")[0] == "AGGRESSIVE"


def test_planner_rejects_bad_input():
    with pytest.raises(ValueError):
        plan_execution(quantity=Decimal("0"), adv=Decimal("100"))
    with pytest.raises(ValueError):
        plan_execution(quantity=Decimal("10"), adv=Decimal("0"))


def test_live_broker_disabled_by_default(monkeypatch):
    monkeypatch.delenv("DELTA_LIVE_BROKER", raising=False)
    assert live_enabled() is False
    with pytest.raises(RuntimeError):
        create_live_broker()


def test_reconcile_wrapper():
    rep = reconcile_oms_vs_broker(("a",), ("a", "b"))
    assert rep.decision == "HALT" and rep.broker_only == ("b",)
