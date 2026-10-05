"""Phase 5 — RoutingPolicy. AUTO never means random: explicit policy inputs.

Phases 6-7 — Paper/live parity + execution modes live here as policy.
Paper and live share Intent->Risk->OMS->Router->Adapter->Reconcile->Audit;
only the terminal adapter differs. Modes are capability policies, not strings.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class RoutingPolicy:
    name: str = "PAPER ONLY"
    eligible_brokers: tuple = ("paper",)
    max_cost_bps: float = 50.0
    max_latency_ms: float = 1000.0
    allocation: str = "single"  # single|split-even|split-liquidity


@dataclass(frozen=True)
class RouteDecision:
    broker_id: str
    account_id: str
    qty: float
    reason: str


def resolve_route(symbol: str, qty: float, policy: RoutingPolicy,
                  candidates: list[dict]) -> list[RouteDecision]:
    """candidates: [{broker_id, account_id, available, cost_bps, latency_ms, ...}]."""
    elig = [c for c in candidates
            if c["broker_id"] in policy.eligible_brokers
            and c.get("available", False)
            and c.get("cost_bps", 0) <= policy.max_cost_bps
            and c.get("latency_ms", 0) <= policy.max_latency_ms]
    if not elig:
        raise ValueError(f"no eligible broker for {symbol} under {policy.name} — blocked")
    elig.sort(key=lambda c: (c.get("cost_bps", 0), c.get("latency_ms", 0)))
    if policy.allocation == "single" or len(elig) == 1:
        best = elig[0]
        return [RouteDecision(best["broker_id"], best["account_id"], qty,
                              f"policy={policy.name} lowest cost/latency")]
    # split-even across eligible (explicit policy, auditable)
    per = qty / len(elig)
    return [RouteDecision(c["broker_id"], c["account_id"], per,
                          f"policy={policy.name} split-even {len(elig)}-way")
            for c in elig]


# Phase 7 — execution modes as capability policy
MODES: dict[str, dict[str, bool]] = {
    "RESEARCH":   {"data": True, "research": True, "paper": False, "live": False, "auto": False},
    "SIM":        {"data": True, "research": True, "paper": True, "live": False, "auto": False},
    "PAPER":      {"data": True, "research": True, "paper": True, "live": False, "auto": True},
    "COPILOT":    {"data": True, "research": True, "paper": True, "live": True, "auto": False},
    "SUPERVISED": {"data": True, "research": True, "paper": True, "live": True, "auto": False},
    "AUTONOMOUS": {"data": True, "research": True, "paper": True, "live": True, "auto": True},
}


def mode_allows(mode: str, cap: str) -> bool:
    try:
        return MODES[mode][cap]
    except KeyError:
        raise ValueError(f"unknown mode/capability {mode}/{cap}")


@dataclass
class LiveActivation:
    broker: str = ""
    account_masked: str = ""
    market_open: bool = False
    risk_safe: bool = False
    kill_armed: bool = False
    auth_valid: bool = False
    permissions_ok: bool = False
    confirmed: bool = False

    def ready(self) -> bool:
        return all([self.broker, self.account_masked, self.market_open,
                    self.risk_safe, self.kill_armed, self.auth_valid,
                    self.permissions_ok, self.confirmed])


__all__ = ["RoutingPolicy", "RouteDecision", "resolve_route",
           "MODES", "mode_allows", "LiveActivation"]
