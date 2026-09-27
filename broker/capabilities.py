from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Capability(str, Enum):
    MARKET_ORDERS = "MARKET_ORDERS"
    LIMIT_ORDERS = "LIMIT_ORDERS"
    STOP_ORDERS = "STOP_ORDERS"
    SHORTING = "SHORTING"
    FRACTIONAL = "FRACTIONAL"
    CANCEL = "CANCEL"
    RECONCILIATION = "RECONCILIATION"
    STREAMING = "STREAMING"


@dataclass(frozen=True)
class BrokerCapabilities:
    broker_name: str
    supported: frozenset[Capability]

    def supports(
        self,
        capability: Capability,
    ) -> bool:
        return capability in self.supported