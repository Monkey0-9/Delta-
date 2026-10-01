"""Typed tool executor (Phase 2).

Schema validation, permission/scope checks, budget enforcement,
idempotency, provenance, and telemetry hooks. No free-text tool syntax.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Mapping

from ai.contracts import (
    Budget,
    EvidenceLedger,
    RiskClass,
    ToolCall,
    ToolDefinition,
    ToolResult,
)


@dataclass(slots=True)
class _BudgetState:
    budget: Budget
    tool_calls: int = 0
    started_at: datetime | None = None

    def start(self) -> None:
        if self.started_at is None:
            self.started_at = datetime.now(timezone.utc)

    def check(self) -> tuple[bool, str]:
        self.start()
        assert self.started_at is not None
        if self.tool_calls >= self.budget.max_tool_calls:
            return False, "budget: max_tool_calls exhausted"
        elapsed = (datetime.now(timezone.utc) - self.started_at).total_seconds()
        if elapsed > self.budget.timeout_s:
            return False, "budget: timeout"
        return True, "ok"


def _check_schema(args: Mapping[str, Any], schema: Mapping[str, Any]) -> tuple[bool, str]:
    """Minimal JSON-schema-subset validation (object/required/types/enum)."""
    if not schema:
        return True, "ok"
    if not isinstance(args, Mapping):
        return False, "arguments must be an object"
    if schema.get("type", "object") != "object":
        return True, "ok"  # non-object schemas out of scope for this executor
    props = schema.get("properties", {})
    for req in schema.get("required", []):
        if req not in args:
            return False, f"missing required argument: {req}"
    for key, val in args.items():
        spec = props.get(key)
        if not spec:
            continue
        want = spec.get("type")
        if want == "string" and not isinstance(val, str):
            return False, f"{key} must be string"
        if want == "number" and not isinstance(val, (int, float)):
            return False, f"{key} must be number"
        if want == "integer" and not isinstance(val, int):
            return False, f"{key} must be integer"
        if want == "boolean" and not isinstance(val, bool):
            return False, f"{key} must be boolean"
        if want == "array" and not isinstance(val, (list, tuple)):
            return False, f"{key} must be array"
        if "enum" in spec and val not in spec["enum"]:
            return False, f"{key} not in enum"
    return True, "ok"


@dataclass(slots=True)
class ExecutorResult:
    run_ledger: EvidenceLedger
    results: list[ToolResult]


class TypedToolExecutor:
    """Executes ToolCalls against registered callables with full gating.

    Deny precedence: unknown tool > schema > permission > scope > budget.
    CRITICAL tools require an explicit authorization token and an
    idempotency key; without both they are denied, never executed.
    """

    def __init__(
        self,
        ledger: EvidenceLedger | None = None,
        authorize: Callable[[ToolCall, ToolDefinition], bool] | None = None,
    ) -> None:
        self._defs: dict[str, ToolDefinition] = {}
        self._fns: dict[str, Callable[..., Any]] = {}
        self._granted: set[tuple[str, str]] = set()  # (agent_id, tool_name)
        self._seen_keys: set[str] = set()
        self.ledger = ledger or EvidenceLedger()
        self._authorize = authorize or (lambda _c, _d: False)

    def register(self, definition: ToolDefinition, fn: Callable[..., Any],
                 overwrite: bool = False) -> None:
        if not callable(fn):
            raise ValueError(f"tool {definition.name!r} fn must be callable")
        if definition.name in self._defs and not overwrite:
            raise ValueError(f"tool {definition.name!r} already registered")
        self._defs[definition.name] = definition
        self._fns[definition.name] = fn

    def grant(self, agent_id: str, tool_name: str) -> None:
        self._granted.add((agent_id, tool_name))

    def execute_step(self, agent_id: str, tool_name: str,
                     arguments: Mapping[str, Any], task_id: Any,
                     auth_token: str | None = None) -> ToolResult:
        """Adapter: plan-step triple -> canonical ToolCall -> execute."""
        from uuid import UUID as _UUID
        from ai.contracts import ToolCall as _ToolCall
        tid = task_id if isinstance(task_id, _UUID) else _UUID(int=0)
        call = _ToolCall(task_id=tid, tool_name=tool_name,
                         arguments=dict(arguments), requested_by=agent_id)
        return self.execute(call, agent_id, auth_token=auth_token)

    def _deny(self, call: ToolCall, reason: str) -> ToolResult:
        import time
        now = datetime.now(timezone.utc)
        res = ToolResult(call_id=call.call_id, status="denied", error=reason,
                         started_at=now, completed_at=now, latency_ms=0.0)
        self.ledger.record_tool(call, res)
        return res

    def execute(self, call: ToolCall, agent_id: str,
                budget: _BudgetState | None = None,
                auth_token: str | None = None) -> ToolResult:
        import time
        start = time.perf_counter_ns()
        now = datetime.now(timezone.utc)

        def finish(status: str, data: Any, error: str | None,
                   refs: tuple[str, ...] = ()) -> ToolResult:
            dt_ms = (time.perf_counter_ns() - start) / 1e6
            res = ToolResult(call_id=call.call_id, status=status, data=data,
                             error=error, evidence_refs=refs,
                             started_at=now,
                             completed_at=datetime.now(timezone.utc),
                             latency_ms=dt_ms)
            self.ledger.record_tool(call, res)
            return res

        definition = self._defs.get(call.tool_name)
        if definition is None:
            return self._deny(call, f"unknown tool: {call.tool_name}")
        ok, msg = _check_schema(call.arguments, definition.input_schema)
        if not ok:
            return self._deny(call, f"schema: {msg}")
        if (agent_id, call.tool_name) not in self._granted:
            return self._deny(call, f"permission: {agent_id} not granted {call.tool_name}")
        if definition.asset_scope and not any(
                str(a) in definition.asset_scope for a in call.arguments.values()):
            # Scope enforced when asset-like arguments are present.
            vals = [str(v) for v in call.arguments.values()]
            if any("/" in v or v.isupper() for v in vals):
                return self._deny(call, "scope: asset outside tool asset_scope")
        if budget is not None:
            good, bmsg = budget.check()
            if not good:
                return self._deny(call, bmsg)
        if definition.risk_class == RiskClass.CRITICAL:
            if not call.idempotency_key:
                return self._deny(call, "critical: idempotency_key required")
            if call.idempotency_key in self._seen_keys:
                return self._deny(call, "critical: duplicate idempotency_key")
            if not auth_token or not self._authorize(call, definition):
                return self._deny(call, "critical: authorization required")
            self._seen_keys.add(call.idempotency_key)
        try:
            import concurrent.futures as _cf
            timeout_s = max(0.001, definition.timeout_ms / 1000.0)
            with _cf.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(self._fns[call.tool_name], **dict(call.arguments))
                data = future.result(timeout=timeout_s)
        except TimeoutError:
            return finish("timeout", None, f"tool timeout after {definition.timeout_ms}ms")
        except Exception as exc:
            return finish("error", None, f"{type(exc).__name__}: {exc}")
        if budget is not None:
            budget.tool_calls += 1
        refs: tuple[str, ...] = ()
        if isinstance(data, Mapping) and "evidence_refs" in data:
            refs = tuple(str(r) for r in data["evidence_refs"])
        return finish("ok", data, None, refs)


__all__ = ["TypedToolExecutor", "ExecutorResult", "_BudgetState"]
