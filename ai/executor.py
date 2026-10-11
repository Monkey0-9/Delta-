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


def _check_type(val: Any, want: str, where: str) -> tuple[bool, str]:
    # bool is a subclass of int: check boolean FIRST so integer rejects bools.
    if want == "boolean":
        return (True, "ok") if isinstance(val, bool) else (False, f"{where} must be boolean")
    if want == "integer":
        return (True, "ok") if isinstance(val, int) and not isinstance(val, bool) else (False, f"{where} must be integer")
    if want == "number":
        return (True, "ok") if isinstance(val, (int, float)) and not isinstance(val, bool) else (False, f"{where} must be number")
    if want == "string":
        return (True, "ok") if isinstance(val, str) else (False, f"{where} must be string")
    if want == "array":
        return (True, "ok") if isinstance(val, (list, tuple)) else (False, f"{where} must be array")
    if want == "object":
        return (True, "ok") if isinstance(val, Mapping) else (False, f"{where} must be object")
    if want == "null":
        return (True, "ok") if val is None else (False, f"{where} must be null")
    return True, "ok"  # unknown type keyword: do not invent rejections


def _check_schema(args: Mapping[str, Any], schema: Mapping[str, Any]) -> tuple[bool, str]:
    """JSON-schema-subset validation: object/required/types/enum/nested
    objects/additionalProperties. Unknown type keywords never reject."""
    return _check_object(args, schema, "$")


def _check_object(args: Any, schema: Mapping[str, Any], where: str) -> tuple[bool, str]:
    if not schema:
        return True, "ok"
    if not isinstance(args, Mapping):
        return False, f"{where}: arguments must be an object"
    if schema.get("type", "object") != "object":
        return True, "ok"  # non-object schemas out of scope for this executor
    props = schema.get("properties", {})
    for req in schema.get("required", []):
        if req not in args:
            return False, f"missing required argument: {req}"
    if schema.get("additionalProperties") is False:
        for key in args:
            if key not in props:
                return False, f"{where}.{key}: prohibited extra field"
    for key, val in args.items():
        spec = props.get(key)
        if not spec:
            continue
        if not isinstance(spec, Mapping):
            continue
        where_k = f"{where}.{key}"
        want = spec.get("type")
        if want:
            ok, msg = _check_type(val, want, where_k)
            if not ok:
                return False, msg
        if "enum" in spec and val not in spec["enum"]:
            return False, f"{where_k} not in enum"
        if want == "object" and isinstance(val, Mapping) and isinstance(spec.get("properties"), Mapping):
            ok, msg = _check_object(val, spec, where_k)
            if not ok:
                return False, msg
        if want == "array" and isinstance(val, (list, tuple)) and isinstance(spec.get("items"), Mapping):
            items_spec = spec["items"]
            for i, item in enumerate(val):
                iw = items_spec.get("type")
                if iw == "object":
                    ok, msg = _check_object(
                        item, items_spec, f"{where_k}[{i}]")
                    if not ok:
                        return False, msg
                elif iw:
                    ok, msg = _check_type(item, iw, f"{where_k}[{i}]")
                    if not ok:
                        return False, msg
                if "enum" in items_spec and item not in items_spec["enum"]:
                    return False, f"{where_k}[{i}] not in enum"
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
        idempotency_path: str | None = None,
    ) -> None:
        self._defs: dict[str, ToolDefinition] = {}
        self._fns: dict[str, Callable[..., Any]] = {}
        self._granted: set[tuple[str, str]] = set()  # (agent_id, tool_name)
        self._seen_keys: set[str] = set()
        self._idempotency_path = idempotency_path
        if idempotency_path is not None:
            self._load_seen_keys()
        self.ledger = ledger or EvidenceLedger()
        self._authorize = authorize or (lambda _c, _d: False)

    def _load_seen_keys(self) -> None:
        """Reload idempotency keys so restarts cannot replay critical tools."""
        import json as _json
        import os as _os

        try:
            with open(str(self._idempotency_path), encoding="utf-8") as f:
                data = _json.load(f)
            if isinstance(data, list):
                self._seen_keys = {str(k) for k in data}
        except FileNotFoundError:
            pass
        except Exception:
            pass  # corrupt file: fail open on load, keys re-accumulate

    def _record_seen_key(self, key: str) -> None:
        self._seen_keys.add(key)
        if self._idempotency_path is None:
            return
        import json as _json
        import os as _os

        try:
            parent = _os.path.dirname(str(self._idempotency_path))
            if parent:
                _os.makedirs(parent, exist_ok=True)
            tmp = str(self._idempotency_path) + f".{_os.getpid()}.tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                _json.dump(sorted(self._seen_keys), f)
                f.flush()
                _os.fsync(f.fileno())
            _os.replace(tmp, str(self._idempotency_path))
        except Exception:
            pass

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
            self._record_seen_key(call.idempotency_key)
        try:
            # P0: the pool is shut down WITHOUT waiting (wait=False,
            # cancel_futures=True). The old `with` block called
            # shutdown(wait=True) on timeout, hanging the caller until the
            # stuck tool returned — a timeout that waits is not a timeout.
            import concurrent.futures as _cf
            timeout_s = max(0.001, definition.timeout_ms / 1000.0)
            pool = _cf.ThreadPoolExecutor(max_workers=1)
            try:
                future = pool.submit(self._fns[call.tool_name], **dict(call.arguments))
                data = future.result(timeout=timeout_s)
            finally:
                pool.shutdown(wait=False, cancel_futures=True)
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
