"""Broker abstraction and execution layer."""

from __future__ import annotations

__all__ = [
    "UniversalBrokerAdapter", "Order", "Position", "AccountInfo", "OrderResult",
    "OrderSide", "OrderType", "OrderStatus", "TimeInForce",
    "RiskGovernor", "KillSwitch",
]

try:
    from .broker_base import (
        UniversalBrokerAdapter, Order, Position, AccountInfo, OrderResult,
        OrderSide, OrderType, OrderStatus, TimeInForce,
    )
except Exception:  # pragma: no cover - optional at import time
    pass

try:
    from .risk_governor import RiskGovernor
except Exception:  # pragma: no cover - optional at import time
    pass

try:
    from .kill_switch import KillSwitch
except Exception:  # pragma: no cover - optional at import time
    pass
