"""Phase 53/96 — API/headless parity contracts. One runtime, many presentations.

TUI, CLI, headless, HTTP, WS all resolve to the same runtime services.
This module declares the contract map; services are injected by the host.
"""
from __future__ import annotations

READ_ENDPOINTS = ("/health", "/status", "/markets/{sym}", "/portfolio",
                  "/risk", "/orders", "/brokers", "/models", "/agents",
                  "/mcp", "/sessions")
WRITE_ENDPOINTS = ("/research", "/backtest", "/simulate", "/orders/stage",
                   "/orders/submit", "/orders/cancel", "/risk/check",
                   "/kill", "/unlock")

# CLI parity: `delta /quote NVDA`, `delta --api`, `delta --json` hit services.
CLI_MAP = {"/quote": "markets.quote", "/risk": "risk.state",
           "/portfolio": "portfolio.snapshot", "/kill": "safety.kill",
           "/status": "system.status"}


def check_parity(services: dict) -> list[str]:
    """Return missing service bindings (empty = full parity)."""
    need = {"markets.quote", "portfolio.snapshot", "risk.state",
            "orders.stage", "orders.submit", "safety.kill", "safety.unlock",
            "system.status"}
    return sorted(need - set(services))


__all__ = ["READ_ENDPOINTS", "WRITE_ENDPOINTS", "CLI_MAP", "check_parity"]
