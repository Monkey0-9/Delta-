from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from core.domain.order import OrderStatus
from execution.engine.engine import OrderManagementSystem
from execution.orders.order_state import ManagedOrder
from risk.pre_trade.validation import TradeIntent


def _intent(**kw) -> TradeIntent:
    base = dict(
        order_id=uuid4(), instrument_id=uuid4(), side="buy",
        quantity=Decimal("10"), idempotency_key=f"k-{uuid4().hex[:8]}", authorized=True,
    )
    base.update(kw)
    return TradeIntent(**base)


def test_oms_approves_clean_intent() -> None:
    oms = OrderManagementSystem()
    res = oms.submit(_intent(), ref_price=Decimal("100"))
    assert res.status == OrderStatus.ACKNOWLEDGED
    assert res.verdict == "approve"


def test_oms_blocks_duplicate_key() -> None:
    oms = OrderManagementSystem()
    intent = _intent(idempotency_key="dup-1")
    assert oms.submit(intent, ref_price=Decimal("100")).verdict == "approve"
    res2 = oms.submit(intent, ref_price=Decimal("100"))
    assert res2.verdict == "block"
    assert res2.status == OrderStatus.REJECTED


def test_oms_blocks_stale_data() -> None:
    oms = OrderManagementSystem()
    res = oms.submit(_intent(), ref_price=Decimal("100"), data_age_s=60.0)
    assert res.verdict == "block"


def test_managed_order_overfill_rejected() -> None:
    o = ManagedOrder(order_id=uuid4(), instrument_id=uuid4(), side="buy", quantity=Decimal("5"))
    with pytest.raises(ValueError):
        o.apply_fill(Decimal("6"))
