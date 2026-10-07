"""Stage-3 N: tool-use gateway — schema validation, approval, audit, idempotency.

AI calls market_data/news_search/portfolio_state (READ_ONLY, no approval).
SIMULATION needs session approval. SENSITIVE needs explicit approval + audit.
Unknown tool raises. Duplicate request_id rejected. Every call audited.
AI never touches the broker (enforced: broker tools absent from registry).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from .contracts import ToolRequest, ToolResult, ToolRisk
from .registry import FinanceToolRegistry


class ToolApprovalRequired(RuntimeError):
    pass


class DuplicateRequest(RuntimeError):
    pass


@dataclass
class ToolGateway:
    registry: FinanceToolRegistry
    audit: list[dict[str, Any]] = field(default_factory=list)
    approved: set[str] = field(default_factory=set)  # request_ids with approval
    seen: set[str] = field(default_factory=set)

    def approve(self, request_id: str) -> None:
        self.approved.add(request_id)

    def call(self, req: ToolRequest) -> ToolResult:
        if req.request_id in self.seen:
            raise DuplicateRequest(f"duplicate request_id {req.request_id}")
        try:
            tool = self.registry.get(req.tool_name)
        except KeyError:
            raise KeyError(f"Unknown finance tool: {req.tool_name}")
        risk = tool.risk
        if risk in (ToolRisk.SIMULATION, ToolRisk.SENSITIVE, "simulation", "sensitive"):
            if req.request_id not in self.approved:
                self._log(req, False, "approval_required")
                raise ToolApprovalRequired(
                    f"{risk} tool {req.tool_name} needs approval for {req.request_id}")
        if not isinstance(req.arguments, dict):
            raise ValueError("arguments must be a dict (schema validation)")
        self.seen.add(req.request_id)
        try:
            data = tool.handler(**req.arguments)
            res = ToolResult(tool_name=req.tool_name, request_id=req.request_id,
                             success=True, data=dict(data))
        except Exception as e:  # noqa: BLE001 — surfaced honestly
            res = ToolResult(tool_name=req.tool_name, request_id=req.request_id,
                             success=False, data={}, error=str(e))
        self._log(req, res.success, res.error or "ok")
        return res

    def _log(self, req: ToolRequest, ok: bool, detail: str) -> None:
        self.audit.append({
            "at": datetime.now(timezone.utc).isoformat(),
            "tool": req.tool_name, "request_id": req.request_id,
            "ok": ok, "detail": detail,
        })


__all__ = ["ToolGateway", "ToolApprovalRequired", "DuplicateRequest"]
