"""Phase 4 — BrokerRegistry: unlimited connections x unlimited accounts.

No broker_name-as-architecture. Each connection declares capabilities;
the command palette only shows operations the connection supports.
PAPER / TEST-SANDBOX / LIVE are distinct environments (never interchangeable).
"""
from __future__ import annotations

from dataclasses import dataclass, field


CAPABILITIES = ("MARKET_DATA", "QUOTES", "HISTORICAL", "DEPTH", "ORDERS",
                "CANCEL", "POSITIONS", "BALANCES", "STREAMING", "OPTIONS",
                "FUTURES", "FX", "CRYPTO")


@dataclass
class BrokerConnection:
    broker_id: str
    provider: str
    environment: str  # PAPER|TEST-SANDBOX|LIVE
    account_id: str
    connection_state: str = "DISCONNECTED"  # CONNECTED|DEGRADED|DISCONNECTED|ERROR
    auth_state: str = "UNAUTHENTICATED"
    capabilities: set = field(default_factory=set)
    supported_order_types: tuple = ("LIMIT", "MARKET")
    supported_instruments: tuple = ("equity",)
    rate_limit_per_min: int = 200
    latency_ms: float | None = None
    permissions: set = field(default_factory=set)

    def supports(self, op: str) -> bool:
        return op in self.capabilities and self.connection_state == "CONNECTED"


class UnknownBroker(Exception):
    pass


class UnknownAccount(Exception):
    pass


class BrokerRegistry:
    def __init__(self):
        self._conns: dict[str, BrokerConnection] = {}
        self._accounts: dict[str, list[str]] = {}  # broker_id -> [account_id]

    def register(self, conn: BrokerConnection) -> None:
        if conn.environment not in ("PAPER", "TEST-SANDBOX", "LIVE"):
            raise ValueError(f"bad environment {conn.environment}")
        self._conns[conn.broker_id] = conn
        self._accounts.setdefault(conn.broker_id, [])
        if conn.account_id not in self._accounts[conn.broker_id]:
            self._accounts[conn.broker_id].append(conn.account_id)

    def get(self, broker_id: str) -> BrokerConnection:
        try:
            return self._conns[broker_id]
        except KeyError:
            raise UnknownBroker(f"unknown broker {broker_id!r} — execution blocked")

    def account_scope(self, broker_id: str, account_id: str) -> BrokerConnection:
        conn = self.get(broker_id)
        if account_id not in self._accounts.get(broker_id, []):
            raise UnknownAccount(f"unknown account {account_id!r} on {broker_id} — blocked")
        return conn

    def available_ops(self, broker_id: str) -> list[str]:
        """Capability-aware palette: only supported ops are offered."""
        conn = self.get(broker_id)
        ops = []
        if conn.supports("QUOTES"):
            ops.append("quote")
        if conn.supports("ORDERS"):
            ops.append("stage order")
        if conn.supports("CANCEL"):
            ops.append("cancel order")
        if conn.supports("POSITIONS"):
            ops += ["positions", "account"]
        return ops

    def scopes(self) -> dict:
        """GLOBAL + per-broker account tree for the TUI."""
        return {"GLOBAL": "all linked accounts",
                **{b: list(a) for b, a in self._accounts.items()}}


__all__ = ["BrokerConnection", "BrokerRegistry", "UnknownBroker",
           "UnknownAccount", "CAPABILITIES"]
