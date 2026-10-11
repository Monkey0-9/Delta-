"""P0: executor schema/scope/timeout/idempotency are real gates."""
from __future__ import annotations

import sys
import time

sys.path.insert(0, ".")

from ai.contracts import RiskClass, ToolCall, ToolDefinition
from ai.executor import TypedToolExecutor, _check_schema


def _tool(**kw):
    base = dict(name="t", permission="p", risk_class=RiskClass.READ_ONLY,
                input_schema={"type": "object"})
    base.update(kw)
    return ToolDefinition(**base)


def test_schema_rejects_extra_fields_and_nesting():
    schema = {"type": "object", "required": ["a"],
              "properties": {
                  "a": {"type": "string"},
                  "n": {"type": "object",
                        "properties": {"x": {"type": "integer"}},
                        "additionalProperties": False},
                  "tags": {"type": "array",
                           "items": {"type": "string",
                                     "enum": ["x", "y"]}}},
              "additionalProperties": False}
    assert _check_schema({"a": "v", "n": {"x": 1}, "tags": ["x"]}, schema)[0]
    assert not _check_schema({"a": "v", "zzz": 1}, schema)[0]  # extra top
    assert not _check_schema({"a": "v", "n": {"x": 1, "y": 2}}, schema)[0]
    assert not _check_schema({"a": "v", "n": {"x": "s"}}, schema)[0]
    assert not _check_schema({"a": "v", "tags": ["z"]}, schema)[0]  # enum
    assert not _check_schema({"b": "v"}, schema)[0]  # missing required


def test_bool_is_not_integer():
    schema = {"type": "object",
              "properties": {"n": {"type": "integer"},
                             "f": {"type": "boolean"}}}
    assert not _check_schema({"n": True, "f": True}, schema)[0]
    assert _check_schema({"n": 3, "f": False}, schema)[0]


def test_timeout_does_not_wait_for_hung_tool():
    ex = TypedToolExecutor()
    ex.register(_tool(timeout_ms=50), lambda: time.sleep(30))
    ex.grant("a", "t")
    t0 = time.perf_counter()
    from uuid import uuid4
    res = ex.execute(ToolCall(tool_name="t", arguments={}, task_id=uuid4()),
                     "a")
    dt = time.perf_counter() - t0
    assert res.status == "timeout", res
    assert dt < 10, f"timeout waited {dt:.1f}s for the hung tool"


def test_idempotency_survives_restart(tmp_path):
    from ai.contracts import ToolCall as TC

    path = str(tmp_path / "keys.json")
    ex = TypedToolExecutor(idempotency_path=path)
    ex.register(ToolDefinition(name="crit", permission="p",
                               risk_class=RiskClass.CRITICAL,
                               side_effect=True,
                               input_schema={"type": "object"}),
                lambda: {"ok": True})
    ex.grant("a", "crit")
    from uuid import uuid4
    call = TC(tool_name="crit", arguments={}, task_id=uuid4(),
              idempotency_key="k-once")
    assert ex.execute(call, "a", auth_token="tok").status == "denied"  # no authorizer
    ex2 = TypedToolExecutor(
        authorize=lambda _c, _d: True, idempotency_path=path)
    ex2.register(ToolDefinition(name="crit", permission="p",
                                risk_class=RiskClass.CRITICAL,
                                side_effect=True,
                                input_schema={"type": "object"}),
                 lambda: {"ok": True})
    ex2.grant("a", "crit")
    assert ex2.execute(call, "a", auth_token="tok").status == "ok"
    # Fresh instance on the same path must refuse the replay.
    ex3 = TypedToolExecutor(
        authorize=lambda _c, _d: True, idempotency_path=path)
    ex3.register(ToolDefinition(name="crit", permission="p",
                                risk_class=RiskClass.CRITICAL,
                                side_effect=True,
                                input_schema={"type": "object"}),
                 lambda: {"ok": True})
    ex3.grant("a", "crit")
    replay = ex3.execute(call, "a", auth_token="tok")
    assert replay.status == "denied" and "duplicate" in (replay.error or "")


def test_router_refuses_unknown_model_visibly():
    """P0: explicit requests for unavailable models fail loudly — never a
    silent substitution that breaks reproducibility and role pinning."""
    import asyncio

    from models.router import ModelRouter

    async def _run():
        from types import SimpleNamespace
        router = ModelRouter(SimpleNamespace(models=[]))
        try:
            await router.generate([{"role": "user", "content": "hi"}],
                                  model_name="does-not-exist")
        except ValueError as exc:
            assert "not available" in str(exc) and "refusing to substitute" in str(exc)
        else:
            raise AssertionError("unknown model must raise, not fall back")

    asyncio.run(_run())
