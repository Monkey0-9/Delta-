from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from core.domain.order import OrderIntent, OrderSide
from execution.fills.fill import Fill

from brokers.interface.broker import (
    BrokerAccount,
    BrokerInterface,
    BrokerOrderResult,
    BrokerPosition,
    MarketSnapshot,
)
from brokers.simulator.clock import SimulationClock
from brokers.simulator.config import SimulatorConfig
from brokers.simulator.market import SimulatedMarket


class SimulatedBroker(BrokerInterface):
    def __init__(
        self,
        *,
        market: SimulatedMarket,
        clock: SimulationClock,
        config: SimulatorConfig | None = None,
    ) -> None:
        self._market = market
        self._clock = clock
        self._config = config or SimulatorConfig()
        self._active_orders: set[UUID] = set()
        self._connected = False
        self._broker_seq = 0

    # --- BrokerInterface conformance (paper) ---

    def connect(self) -> None:
        self._connected = True

    def disconnect(self) -> None:
        self._connected = False

    def is_connected(self) -> bool:
        return self._connected

    def get_account(self) -> BrokerAccount:
        return BrokerAccount(account_id="paper", currency="USD", cash=Decimal("1000000"), buying_power=Decimal("1000000"))

    def get_positions(self) -> tuple[BrokerPosition, ...]:
        return ()

    def get_orders(self) -> tuple[dict[str, object], ...]:
        return tuple({"order_id": str(o)} for o in self._active_orders)

    def get_market_data(self, instrument_id: UUID) -> MarketSnapshot:
        return self._market.get(instrument_id)

    def place_order(self, order: OrderIntent, *, idempotency_key: str) -> BrokerOrderResult:
        if not idempotency_key:
            return BrokerOrderResult("", False, "rejected", "missing idempotency_key")
        try:
            fills = self.submit_order(order)
        except ValueError as exc:
            return BrokerOrderResult("", False, "rejected", str(exc))
        self._broker_seq += 1
        return BrokerOrderResult(f"paper-{self._broker_seq}", True, "accepted" if fills else "no-liquidity")

    def get_order_status(self, broker_order_id: str) -> BrokerOrderResult:
        return BrokerOrderResult(broker_order_id, True, "open")

    def submit_order(
        self,
        order: OrderIntent,
    ) -> tuple[Fill, ...]:
        order_id = order.order_id

        if order_id in self._active_orders:
            raise ValueError(
                f"Duplicate order submission: {order_id}"
            )

        snapshot = self._market.get(order.instrument_id)

        if snapshot.available_quantity <= Decimal("0"):
            raise ValueError(
                "No available market liquidity."
            )

        fill_quantity = min(
            order.quantity,
            snapshot.available_quantity
            * self._config.max_participation_rate,
        )

        if fill_quantity <= Decimal("0"):
            return ()

        if order.side == OrderSide.BUY:
            base_price = snapshot.ask
        else:
            base_price = snapshot.bid

        slippage_multiplier = (
            Decimal("1")
            + self._config.slippage_bps / Decimal("10000")
        )

        if order.side == OrderSide.BUY:
            execution_price = (
                base_price * slippage_multiplier
            )
        else:
            execution_price = (
                base_price / slippage_multiplier
            )

        fee = (
            fill_quantity
            * execution_price
            * self._config.commission_rate
        )

        slippage = (
            abs(execution_price - base_price)
            * fill_quantity
        )

        self._active_orders.add(order_id)

        return (
            Fill(
                order_id=order_id,
                instrument_id=order.instrument_id,
                quantity=fill_quantity,
                price=execution_price,
                fee=fee,
                slippage=slippage,
                executed_at=self._clock.now,
            ),
        )

    def cancel_order(
        self,
        order_id: UUID,
    ) -> bool:
        if order_id not in self._active_orders:
            return False

        self._active_orders.remove(order_id)
        return True

    def get_market_snapshot(
        self,
        instrument_id: UUID,
    ):
        return self._market.get(instrument_id)