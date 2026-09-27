from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from brokers.interface.broker import MarketSnapshot
from brokers.simulator.broker import SimulatedBroker
from brokers.simulator.clock import SimulationClock
from brokers.simulator.config import SimulatorConfig
from brokers.simulator.market import SimulatedMarket
from execution.reconciliation.reconciler import (
    ExecutionReconciler,
    ReconciliationError,
)


def make_market() -> tuple[UUID, SimulatedBroker]:
    """Create a deterministic simulated market and broker."""

    instrument_id: UUID = uuid4()

    snapshot = MarketSnapshot(
        instrument_id=instrument_id,
        bid=Decimal("99"),
        ask=Decimal("101"),
        last=Decimal("100"),
        available_quantity=Decimal("1000"),
    )

    market = SimulatedMarket(
        snapshots={
            instrument_id: snapshot,
        }
    )

    clock = SimulationClock(
        datetime(
            2026,
            1,
            1,
            tzinfo=timezone.utc,
        )
    )

    config = SimulatorConfig(
        commission_rate=Decimal("0.001"),
        slippage_bps=Decimal("5"),
    )

    broker = SimulatedBroker(
        market=market,
        clock=clock,
        config=config,
    )

    return instrument_id, broker


def test_market_snapshot() -> None:
    instrument_id, broker = make_market()

    snapshot = broker.get_market_snapshot(
        instrument_id
    )

    assert snapshot.instrument_id == instrument_id
    assert snapshot.bid == Decimal("99")
    assert snapshot.ask == Decimal("101")
    assert snapshot.last == Decimal("100")
    assert snapshot.available_quantity == Decimal("1000")


def test_simulated_buy_fill() -> None:
    instrument_id, broker = make_market()

    from core.domain.order import Order, OrderSide

    order = Order(
        instrument_id=instrument_id,
        side=OrderSide.BUY,
        quantity=Decimal("10"),
    )

    fills = broker.submit_order(order)

    assert len(fills) == 1

    fill = fills[0]

    assert fill.order_id == order.order_id
    assert fill.instrument_id == instrument_id
    assert fill.quantity == Decimal("10")

    # Buy execution must occur at or above the ask
    # because the simulator includes positive slippage.
    assert fill.price > Decimal("101")

    assert fill.fee > Decimal("0")
    assert fill.slippage > Decimal("0")


def test_duplicate_order_is_rejected() -> None:
    instrument_id, broker = make_market()

    from core.domain.order import Order, OrderSide

    order = Order(
        instrument_id=instrument_id,
        side=OrderSide.BUY,
        quantity=Decimal("10"),
    )

    first_fills = broker.submit_order(order)

    assert len(first_fills) == 1

    with pytest.raises(ValueError, match="Duplicate order"):
        broker.submit_order(order)


def test_fill_cannot_exceed_order() -> None:
    instrument_id, broker = make_market()

    from core.domain.order import Order, OrderSide

    order = Order(
        instrument_id=instrument_id,
        side=OrderSide.BUY,
        quantity=Decimal("10"),
    )

    fills = broker.submit_order(order)

    assert len(fills) == 1

    fill = fills[0]

    with pytest.raises(
        ReconciliationError,
        match="Fill exceeds remaining order quantity",
    ):
        ExecutionReconciler.validate_fill(
            order_id=order.order_id,
            expected_quantity=Decimal("5"),
            already_filled=Decimal("0"),
            fill=fill,
        )


def test_clock_is_deterministic() -> None:
    start = datetime(
        2026,
        1,
        1,
        tzinfo=timezone.utc,
    )

    clock = SimulationClock(start)

    first = clock.now

    clock.advance(1.5)

    assert clock.now == datetime(
        2026,
        1,
        1,
        0,
        0,
        1,
        500000,
        tzinfo=timezone.utc,
    )

    assert (
        clock.now - first
    ).total_seconds() == 1.5


def test_sell_execution_is_below_bid_with_slippage() -> None:
    instrument_id, broker = make_market()

    from core.domain.order import Order, OrderSide

    order = Order(
        instrument_id=instrument_id,
        side=OrderSide.SELL,
        quantity=Decimal("10"),
    )

    fills = broker.submit_order(order)

    assert len(fills) == 1

    fill = fills[0]

    # Sell execution should be below the bid
    # when positive slippage is applied.
    assert fill.price < Decimal("99")

    assert fill.quantity == Decimal("10")


def test_partial_fill_respects_participation_limit() -> None:
    instrument_id, _ = make_market()

    from core.domain.order import Order, OrderSide

    market = SimulatedMarket(
        snapshots={
            instrument_id: MarketSnapshot(
                instrument_id=instrument_id,
                bid=Decimal("99"),
                ask=Decimal("101"),
                last=Decimal("100"),
                available_quantity=Decimal("100"),
            )
        }
    )

    clock = SimulationClock(
        datetime(
            2026,
            1,
            1,
            tzinfo=timezone.utc,
        )
    )

    broker = SimulatedBroker(
        market=market,
        clock=clock,
        config=SimulatorConfig(
            commission_rate=Decimal("0"),
            slippage_bps=Decimal("0"),
            max_participation_rate=Decimal("0.25"),
        ),
    )

    order = Order(
        instrument_id=instrument_id,
        side=OrderSide.BUY,
        quantity=Decimal("100"),
    )

    fills = broker.submit_order(order)

    assert len(fills) == 1

    assert fills[0].quantity == Decimal("25")


def test_cancel_order() -> None:
    instrument_id, broker = make_market()

    from core.domain.order import Order, OrderSide

    order = Order(
        instrument_id=instrument_id,
        side=OrderSide.BUY,
        quantity=Decimal("10"),
    )

    broker.submit_order(order)

    assert broker.cancel_order(order.order_id) is True

    # Second cancellation must be idempotently unsuccessful.
    assert broker.cancel_order(order.order_id) is False