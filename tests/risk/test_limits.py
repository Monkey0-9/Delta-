"""Risk limits: paper.yaml parity, VaR wiring, kill-switch halt."""
from decimal import Decimal
from uuid import uuid4

from risk.firewall.firewall import RiskFirewall
from risk.limits.limits import RiskLimits
from risk.pre_trade.validation import TradeIntent


def _intent(**kw):
    base = dict(
        order_id=uuid4(),
        instrument_id=uuid4(),
        side="buy",
        quantity=Decimal("10"),
        idempotency_key="k-risk-1",
        authorized=True,
    )
    base.update(kw)
    return TradeIntent(**base)


def test_paper_yaml_loads():
    limits = RiskLimits.from_paper_yaml("config/paper.yaml")
    assert limits.max_order_qty == Decimal("1000")
    assert limits.stale_data_ttl_s == 5
    assert limits.version == "limits-v1"


def test_var_breach_blocks():
    limits = RiskLimits(max_var_notional=Decimal("100"))
    fw = RiskFirewall(limits=limits)
    d = fw.check(_intent(idempotency_key="k-var-1"), portfolio_var=Decimal("500"))
    assert d.verdict.name == "BLOCK"
    assert "var_limit_breach" in d.reasons


def test_kill_switch_halts_firewall():
    fw = RiskFirewall()
    fw.kill_switch.activate(actor="ops")
    d = fw.check(_intent(idempotency_key="k-kill-1"))
    assert d.verdict.name == "BLOCK"
    assert "kill_switch_active" in d.reasons


def test_notional_vs_qty_separation_p0():
    """P0: $10k notional cap must BLOCK 100sh @ $500 despite qty passing."""
    limits = RiskLimits(
        max_order_qty=Decimal("1000"),
        max_order_notional=Decimal("10000"),
        max_intraday_position=Decimal("5000"),
        max_position_notional=Decimal("10000"),
    )
    fw = RiskFirewall(limits=limits)
    d = fw.check(
        _intent(idempotency_key="k-p0-1", quantity=Decimal("100")),
        ref_price=Decimal("500"),
    )
    assert d.verdict.name == "BLOCK"
    assert "max_order_notional_breach" in d.reasons
    assert "max_order_qty_breach" not in d.reasons


def test_position_notional_breach_p0():
    limits = RiskLimits(max_position_notional=Decimal("10000"))
    fw = RiskFirewall(limits=limits)
    d = fw.check(
        _intent(idempotency_key="k-p0-2", quantity=Decimal("10")),
        ref_price=Decimal("100"),
        current_position_notional=Decimal("9500"),
    )
    assert d.verdict.name == "BLOCK"
    assert "position_notional_breach" in d.reasons


def test_oms_forwards_var_to_firewall_p0():
    from execution.engine.engine import OrderManagementSystem

    limits = RiskLimits(max_var_notional=Decimal("100"))
    oms = OrderManagementSystem(risk=RiskFirewall(limits=limits))
    res = oms.submit(_intent(idempotency_key="k-p0-3"), portfolio_var=Decimal("500"))
    assert res.verdict == "block"
    assert "var_limit_breach" in res.reasons
