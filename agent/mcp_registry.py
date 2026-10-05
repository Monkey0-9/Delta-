"""Phase 11 — MCP registry: servers/tools/health/latency/permissions.

Never CONNECTED-by-config: status reflects runtime reports only.
"""
from __future__ import annotations

from dataclasses import dataclass, field


STATUSES = ("CONNECTED", "DEGRADED", "DISCONNECTED", "ERROR", "DISABLED")


@dataclass
class McpServer:
    name: str
    status: str = "DISCONNECTED"
    version: str = ""
    latency_ms: float | None = None
    tools: tuple = ()
    permissions: tuple = ()
    last_error: str = ""


class McpRegistry:
    def __init__(self):
        self._servers: dict[str, McpServer] = {}

    def report(self, srv: McpServer) -> None:
        if srv.status not in STATUSES:
            raise ValueError(f"bad MCP status {srv.status}")
        self._servers[srv.name] = srv

    def get(self, name: str) -> McpServer:
        try:
            return self._servers[name]
        except KeyError:
            raise ValueError(f"unknown MCP server {name!r}")

    def tools(self) -> dict[str, str]:
        out = {}
        for s in self._servers.values():
            if s.status == "CONNECTED":
                for t in s.tools:
                    out[t] = s.name
        return out

    def dashboard(self) -> dict[str, list[str]]:
        groups: dict[str, list[str]] = {s: [] for s in STATUSES}
        for s in self._servers.values():
            groups[s.status].append(s.name)
        return groups


__all__ = ["STATUSES", "McpServer", "McpRegistry"]
