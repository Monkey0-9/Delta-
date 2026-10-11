"""P0-3/P0-4: gateway must separate approval from submission and require roles.

- Approval without a broker is RISK_APPROVED only (submitted=False); it must
  never be interpretable as a completed submission.
- A broker acknowledgement advances SUBMITTED -> ACKNOWLEDGED; an explicit
  broker rejection lands REJECTED.
- role=None is refused on the production path (missing_role); legacy routing
  survives only behind explicit require_role=False.
"""
from __future__ import annotations

import sys
from decimal import Decimal
from uuid import uuid4

import pytest

sys.path.insert(0, ".")

from core.domain.order import Order, OrderSide, OrderStatus, OrderType
from core.oms.gateway import OrderGateway
from risk.firewall.firewall import RiskFirewall


def _order(**kw):
    base = dict(instrument_id=uuid4(), side=OrderSide.BUY,
                quantity=Decimal("10"), order_type=OrderType.MARKET)
    base.update(kw)
    return Order(**base)


def _gw(**kw):
    return OrderGateway(firewall=RiskFirewall(), **kw)


def test_approval_without_broker_is_not_a_submission():
    d = _gw().submit(_order(), ref_price=Decimal("100"), authorized=True,
                     role="risk_officer")
    assert d.approved is True
    assert d.submitted is False, "approval-only must not read as submitted"
    assert d.order.status == OrderStatus.RISK_APPROVED
    assert d.audit_entry.get("submitted") is False


def test_broker_ack_advances_to_acknowledged():
    d = _gw().submit(_order(), ref_price=Decimal("100"), authorized=True,
                     role="risk_officer", broker=lambda o: {"ack": "ok"})
    assert d.approved is True
    assert d.submitted is True
    assert d.order.status == OrderStatus.ACKNOWLEDGED


def test_broker_rejection_lands_rejected():
    d = _gw().submit(_order(), ref_price=Decimal("100"), authorized=True,
                     role="risk_officer",
                     broker=lambda o: {"accepted": False, "reason": "HALTED"})
    assert d.approved is False
    assert d.submitted is False
    assert d.order.status == OrderStatus.REJECTED
    assert "broker_rejected" in d.reasons


def test_missing_role_refused_on_production_path():
    d = _gw().submit(_order(), ref_price=Decimal("100"), authorized=True)
    assert d.approved is False
    assert d.submitted is False
    assert any("missing_role" in r for r in d.reasons)
    assert d.audit_entry["verdict"] == "block"


def test_underprivileged_role_refused():
    d = _gw().submit(_order(), ref_price=Decimal("100"), authorized=True,
                     role="researcher")
    assert d.approved is False
    assert any("unauthorized_role" in r for r in d.reasons)


def test_explicit_legacy_gateway_still_warns_and_routes():
    with pytest.warns(FutureWarning):
        d = _gw(require_role=False).submit(
            _order(), ref_price=Decimal("100"), authorized=True)
    assert d.approved is True
    assert d.audit_entry.get("legacy_bypass") is True


def test_trade_yes_flag_never_prompts(monkeypatch):
    """P0-2 backend half: --yes executes the gate/submit path without an
    interactive prompt (the ticket already confirmed)."""
    import sys

    sys.path.insert(0, "tests")
    from test_automation_gate import _frame, _Router

    from delta_os.repl import Terminal

    t = Terminal()
    t.brain.data_router = _Router({"BULL": _frame("up")}, "TIER1")
    t.data = t.brain.data_router

    def _no_prompt(*a, **k):
        raise AssertionError("interactive prompt must not fire with --yes")

    monkeypatch.setattr("builtins.input", _no_prompt)
    out, _ = t.handle("/trade BULL buy 10 --yes")
    assert "submitted" in out, out
    assert len(t.router.paper._ledger.orders) == 1


def test_firewall_enforces_gross_and_leverage_ceilings():
    """P2/H: portfolio ceilings block over-limit intents; unevaluable
    context fails closed; absent context skips (documented)."""
    from decimal import Decimal
    from uuid import uuid4

    from risk.firewall.firewall import RiskFirewall
    from risk.limits.limits import RiskLimits
    from risk.pre_trade.validation import TradeIntent

    fw = RiskFirewall(limits=RiskLimits(
        max_gross_exposure=Decimal("10000"), max_leverage=Decimal("2"),
        max_order_qty=Decimal("10") ** 9,
        max_order_notional=Decimal("10") ** 12,
        max_intraday_position=Decimal("10") ** 9,
        max_position_notional=Decimal("10") ** 12))

    def _intent(qty):
        return TradeIntent(order_id=uuid4(), instrument_id=uuid4(),
                           side="buy", quantity=Decimal(str(qty)),
                           idempotency_key=f"k-{qty}-{uuid4()}",
                           authorized=True, price_source="real")

    d = fw.check(_intent(50), ref_price=Decimal("100"),
                 portfolio_gross=Decimal("4000"),
                 portfolio_equity=Decimal("10000"))
    assert d.verdict.value == "approve", d.reasons
    d = fw.check(_intent(70), ref_price=Decimal("100"),
                 portfolio_gross=Decimal("4000"),
                 portfolio_equity=Decimal("10000"))
    assert d.verdict.value == "block"
    assert "gross_exposure_breach" in d.reasons  # 4000+7000 > 10000
    d = fw.check(_intent(50), ref_price=Decimal("100"),
                 portfolio_gross=Decimal("4000"),
                 portfolio_equity=Decimal("4000"))
    assert d.verdict.value == "block"
    assert "leverage_breach" in d.reasons  # 9000/4000 = 2.25 > 2
    d = fw.check(_intent(50), ref_price=Decimal("100"),
                 portfolio_gross=Decimal("4000"),
                 portfolio_equity=None)
    assert d.verdict.value == "block"
    assert "portfolio_ceiling_unevaluable_missing_input" in d.reasons
