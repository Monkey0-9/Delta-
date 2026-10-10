"""Institutional test suite for DELTA Java LMAX Disruptor Execution Gateway."""
import uuid

import pytest

from execution.adapters.java_gateway_adapter import JavaGatewayAdapter


@pytest.fixture(scope="module")
def java_gateway():
    import shutil
    if shutil.which("java") is None:
        pytest.skip("java not available in this environment — Java lane UNAVAILABLE (PAPER/SIM Python OMS remains authoritative).")
    adapter = JavaGatewayAdapter(port=9005, auto_spawn=True)
    adapter.start()
    yield adapter
    adapter.stop()


def test_java_disruptor_order_matching_and_fifo_fill(java_gateway):
    uid = uuid.uuid4().hex[:6].upper()
    sym = f"NVDA_{uid}"
    sell_id = f"SELL-{uid}"
    buy_id = f"BUY-{uid}"

    # 1. Place Resting Sell Limit: 100 NVDA @ $185.00
    resting = java_gateway.match_order(
        cl_ord_id=sell_id,
        symbol=sym,
        side="SELL",
        order_type="LMT",
        price_dollars=185.00,
        quantity=100,
    )
    assert len(resting) == 1
    assert resting[0]["cl_ord_id"] == sell_id
    assert resting[0]["exec_type"] == 0  # New order ACK

    # 2. Place Aggressive Buy Limit: 60 NVDA @ $185.00 (Crosses book)
    agg_buy = java_gateway.match_order(
        cl_ord_id=buy_id,
        symbol=sym,
        side="BUY",
        order_type="LMT",
        price_dollars=185.00,
        quantity=60,
    )
    assert len(agg_buy) == 2  # Match fills both buyer and resting seller

    # Verify Buyer Fill
    buyer_fill = next(r for r in agg_buy if r["cl_ord_id"] == buy_id)
    assert buyer_fill["fill_qty"] == 60
    assert buyer_fill["price"] == 185.00
    assert buyer_fill["exec_type"] == 2  # Full Fill
    assert "35=8" in buyer_fill["fix_report"]  # FIX ExecutionReport tag

    # Verify Seller Partial Fill
    seller_fill = next(r for r in agg_buy if r["cl_ord_id"] == sell_id)
    assert seller_fill["fill_qty"] == 60
    assert seller_fill["cum_qty"] == 60
    assert seller_fill["exec_type"] == 1  # Partial Fill


def test_java_order_cancel(java_gateway):
    # Place Limit Order
    java_gateway.match_order(
        cl_ord_id="CANCEL-ME-01",
        symbol="SPY",
        side="BUY",
        order_type="LMT",
        price_dollars=500.00,
        quantity=50,
    )
    # Cancel Order
    canceled = java_gateway.cancel_order("SPY", "CANCEL-ME-01")
    assert canceled is True
