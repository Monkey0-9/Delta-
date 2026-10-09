"""Bridge unlock regression tests (quality-review fixes)."""
from __future__ import annotations

from delta_os.bridge import DeltaBridge

_TOKEN = "test-token-123"


def _bridge(monkeypatch) -> DeltaBridge:
    monkeypatch.setenv("DELTA_UNLOCK_TOKEN", _TOKEN)
    return DeltaBridge()


def test_kill_then_unlock_valid_token(monkeypatch):
    b = _bridge(monkeypatch)
    kill = b.kill_switch(confirm=True)
    assert kill["status"] == "HALTED"
    res = b.unlock(actor="trader", reason="manual_override", token=_TOKEN)
    assert res["status"] == "UNLOCKED"
    assert res["safety_mode"] == "MANUAL"
    assert b.term.safety.mode == "MANUAL"


def test_unlock_safety_exception_is_denied_not_raised(monkeypatch):
    b = _bridge(monkeypatch)
    assert b.kill_switch(confirm=True)["status"] == "HALTED"

    def _boom(actor, reason):
        raise RuntimeError("boom")

    monkeypatch.setattr(b.term.safety, "unlock", _boom)
    res = b.unlock(actor="trader", reason="manual_override", token=_TOKEN)
    assert res["status"] == "DENIED"
    assert str(getattr(b.term.safety, "mode", "")).upper() == "HALTED"


def test_unlock_whitespace_actor_denied_without_handle(monkeypatch):
    b = _bridge(monkeypatch)
    calls: list = []
    orig = b.term.handle

    def _spy(text):
        calls.append(text)
        return orig(text)

    monkeypatch.setattr(b.term, "handle", _spy)
    assert b.unlock(actor="bad actor", reason="manual_override", token=_TOKEN)["status"] == "DENIED"
    assert b.unlock(actor="", reason="manual_override", token=_TOKEN)["status"] == "DENIED"
    assert calls == []


def test_unlock_wrong_token_denied(monkeypatch):
    b = _bridge(monkeypatch)
    res = b.unlock(actor="trader", reason="manual_override", token="wrong-token")
    assert res["status"] == "DENIED"
