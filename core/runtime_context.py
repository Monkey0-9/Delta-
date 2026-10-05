"""Phase 1 — Canonical DeltaRuntimeContext (single source of truth for every view).

NO_DEMO_STATE_IN_PRODUCTION_RUNTIME: financial fields default to None
(UNAVAILABLE) — never to fabricated prices/balances. Views render UNAVAILABLE
until a real runtime snapshot arrives via apply_snapshot().
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SessionCtx:
    session_id: str = ""
    workspace_id: str = "desk"
    created_at: str = ""
    last_activity: str = ""
    mode: str = "PAPER"


@dataclass
class UserCtx:
    user_id: str = ""
    role: str = "trader"


@dataclass
class FocusCtx:
    instrument_id: str = ""
    symbol: str = ""
    venue: str = ""
    currency: str = ""


@dataclass
class MarketCtx:
    global_status: str = "UNKNOWN"
    timezone: str = "UTC"
    active_exchange: str = ""


@dataclass
class DataCtx:
    quality: str = "UNAVAILABLE"  # LIVE|DELAYED|HISTORICAL|PAPER|SIM|SYNTHETIC|STALE|DEGRADED|UNAVAILABLE
    provider: str = ""
    latency_ms: float | None = None
    asof: str = ""


@dataclass
class PortfolioCtx:
    account: str = ""
    equity: float | None = None
    cash: float | None = None
    buying_power: float | None = None
    positions: list = field(default_factory=list)
    exposure_gross: float | None = None
    exposure_net: float | None = None


@dataclass
class RiskCtx:
    state: str = "UNKNOWN"  # SAFE|WARNING|BREACH|HALTED|UNKNOWN
    limits: dict = field(default_factory=dict)
    utilization: dict = field(default_factory=dict)
    alerts: list = field(default_factory=list)


@dataclass
class ExecutionCtx:
    environment: str = "PAPER"
    routing_policy: str = "PAPER ONLY"
    working_orders: list = field(default_factory=list)


@dataclass
class BrokerCtx:
    connections: dict = field(default_factory=dict)
    accounts: dict = field(default_factory=dict)
    permissions: dict = field(default_factory=dict)


@dataclass
class ModelCtx:
    provider: str = ""
    model: str = ""
    variant: str = ""
    effort: str = "MEDIUM"  # LOW|MEDIUM|HIGH|XHIGH|AUTO
    thinking_display: str = "SUMMARY"  # OFF|SUMMARY|ACTIVITY


@dataclass
class AgentCtx:
    active_agent: str = "delta"
    tasks: list = field(default_factory=list)


@dataclass
class McpCtx:
    servers: dict = field(default_factory=dict)
    tools: dict = field(default_factory=dict)


@dataclass
class PermissionCtx:
    grants: dict = field(default_factory=dict)


@dataclass
class TaskCtx:
    running: list = field(default_factory=list)
    queued: list = field(default_factory=list)


@dataclass
class SystemCtx:
    tui: str = "READY"
    runtime: str = "STARTING"
    health: dict = field(default_factory=dict)


@dataclass
class AuditCtx:
    last_event: str = ""
    chain_status: str = "UNKNOWN"


@dataclass
class DeltaRuntimeContext:
    """Heart of the TUI. Every view reads this; nothing invents state."""
    session: SessionCtx = field(default_factory=SessionCtx)
    workspace: str = "desk"
    user: UserCtx = field(default_factory=UserCtx)
    instrument: FocusCtx = field(default_factory=FocusCtx)
    market: MarketCtx = field(default_factory=MarketCtx)
    portfolio: PortfolioCtx = field(default_factory=PortfolioCtx)
    risk: RiskCtx = field(default_factory=RiskCtx)
    execution: ExecutionCtx = field(default_factory=ExecutionCtx)
    brokers: BrokerCtx = field(default_factory=BrokerCtx)
    accounts: dict = field(default_factory=dict)
    models: ModelCtx = field(default_factory=ModelCtx)
    agents: AgentCtx = field(default_factory=AgentCtx)
    mcp: McpCtx = field(default_factory=McpCtx)
    data: DataCtx = field(default_factory=DataCtx)
    permissions: PermissionCtx = field(default_factory=PermissionCtx)
    tasks: TaskCtx = field(default_factory=TaskCtx)
    system: SystemCtx = field(default_factory=SystemCtx)
    audit: AuditCtx = field(default_factory=AuditCtx)

    def top_bar(self) -> str:
        p = self.portfolio
        eq = f"{p.equity:,.0f}" if p.equity is not None else "UNAVAILABLE"
        return (f"DELTA | {self.session.session_id or 'no-session'} | MODE:{self.session.mode} | "
                f"BROKER:{self.execution.environment} | DATA:{self.data.quality} | "
                f"RISK:{self.risk.state} | EQUITY:{eq}")

    def desk_snapshot(self) -> dict:
        return {"top_bar": self.top_bar(), "workspace": self.workspace,
                "focus": self.instrument.symbol or "NONE",
                "data": self.data.quality, "risk": self.risk.state,
                "mode": self.session.mode}

    def apply_snapshot(self, snap: dict) -> None:
        """Authoritative runtime -> context. Unknown keys ignored (fail-closed)."""
        pf = snap.get("portfolio", {})
        if "equity" in pf:
            self.portfolio.equity = pf["equity"]
        if "cash" in pf:
            self.portfolio.cash = pf["cash"]
        if snap.get("risk", {}).get("state"):
            self.risk.state = snap["risk"]["state"]
        if snap.get("data", {}).get("quality"):
            self.data.quality = snap["data"]["quality"]


__all__ = ["DeltaRuntimeContext", "SessionCtx", "UserCtx", "FocusCtx",
           "MarketCtx", "DataCtx", "PortfolioCtx", "RiskCtx", "ExecutionCtx",
           "BrokerCtx", "ModelCtx", "AgentCtx", "McpCtx", "PermissionCtx",
           "TaskCtx", "SystemCtx", "AuditCtx"]
