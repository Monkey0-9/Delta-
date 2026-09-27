from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Mapping


class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"
    STOP_LIMIT = "STOP_LIMIT"


class TimeInForce(str, Enum):
    DAY = "DAY"
    IOC = "IOC"
    FOK = "FOK"
    GTC = "GTC"


@dataclass(frozen=True)
class BrokerOrder:
    client_order_id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: Decimal
    limit_price: Decimal | None = None
    stop_price: Decimal | None = None
    time_in_force: TimeInForce = TimeInForce.DAY


@dataclass(frozen=True)
class BrokerOrderResult:
    broker_order_id: str
    client_order_id: str
    status: str
    raw: Mapping


@dataclass(frozen=True)
class BrokerPosition:
    symbol: str
    quantity: Decimal
    average_price: Decimal


@dataclass(frozen=True)
class BrokerAccount:
    account_id: str
    equity: Decimal
    cash: Decimal
    buying_power: Decimal


class BrokerAdapter(ABC):

    @abstractmethod
    def health(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def account(self) -> BrokerAccount:
        raise NotImplementedError

    @abstractmethod
    def positions(self) -> list[BrokerPosition]:
        raise NotImplementedError

    @abstractmethod
    def submit(
        self,
        order: BrokerOrder,
    ) -> BrokerOrderResult:
        raise NotImplementedError

    @abstractmethod
    def cancel(
        self,
        broker_order_id: str,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def order_status(
        self,
        broker_order_id: str,
    ) -> BrokerOrderResult:
        raise NotImplementedError

    @abstractmethod
    def reconcile(self) -> list[BrokerOrderResult]:
        raise NotImplementedError