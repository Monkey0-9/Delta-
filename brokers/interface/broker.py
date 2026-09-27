from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class MarketSnapshot:
    """
    Deterministic market snapshot shared by the simulator
    and production broker adapters.
    """

    instrument_id: UUID
    bid: Decimal
    ask: Decimal
    last: Decimal
    available_quantity: Decimal

    def __post_init__(self) -> None:
        if self.bid < Decimal("0"):
            raise ValueError("bid cannot be negative.")

        if self.ask < Decimal("0"):
            raise ValueError("ask cannot be negative.")

        if self.last < Decimal("0"):
            raise ValueError("last cannot be negative.")

        if self.available_quantity < Decimal("0"):
            raise ValueError("available_quantity cannot be negative.")

        if self.ask < self.bid:
            raise ValueError("ask cannot be lower than bid.")


@dataclass(frozen=True, slots=True)
class BrokerAccount:
    account_id: str
    currency: str
    cash: Decimal
    buying_power: Decimal


@dataclass(frozen=True, slots=True)
class BrokerPosition:
    instrument_id: UUID
    quantity: Decimal
    average_price: Decimal


@dataclass(frozen=True, slots=True)
class BrokerOrderResult:
    broker_order_id: str
    accepted: bool
    status: str
    message: str = ""


class BrokerInterface(Protocol):
    """
    Structural broker contract.

    Implementations do not need to inherit from this protocol.
    This preserves compatibility with the deterministic simulator
    while providing a strict contract for production adapters.
    """

    def connect(self) -> None:
        ...

    def disconnect(self) -> None:
        ...

    def is_connected(self) -> bool:
        ...

    def get_account(self) -> BrokerAccount:
        ...

    def get_positions(self) -> tuple[BrokerPosition, ...]:
        ...

    def get_orders(self) -> tuple[dict[str, Any], ...]:
        ...

    def get_market_data(
        self,
        instrument_id: UUID,
    ) -> MarketSnapshot:
        ...

    def place_order(
        self,
        order: Any,
        *,
        idempotency_key: str,
    ) -> BrokerOrderResult:
        ...

    def cancel_order(
        self,
        broker_order_id: str,
    ) -> BrokerOrderResult:
        ...

    def get_order_status(
        self,
        broker_order_id: str,
    ) -> BrokerOrderResult:
        ...