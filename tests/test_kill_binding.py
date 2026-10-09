"""A2 kill-enforcement binding tests (fail-closed, minimal scope).

Covers:
- direct safety.unlock with wrong token is denied (stays HALTED);
  no-token direct calls keep legacy behavior; correct token unlocks.
- governance KillSwitch activate/deactivate propagate to bound board,
  and is_active() reflects the board when bound.
- breaker reset()/close() require explicit confirm=True (refused otherwise,
  no state change); optional token checked against DELTA_UNLOCK_TOKEN.
- HALT marker round-trips through save/restore (fail-closed restart).
"""
from __future__ import annotations

import sys

import pytest

sys.path.insert(0, ".")


@pytest.fixture
def _isolated_session(monkeypatch, tmp_path):
    """Point the canonical session-file helper at a tmp file (hermetic marker)."""
    import delta_os.safety as _safety

    p = tmp_path / "session.json"

    monkeypatch.setattr(_safety, "_session_path", lambda: p)
    return p


def test_direct_unlock_wrong_token_denied(monkeypatch, _isolated_session):
    from delta_os.safety import SafetyError, SafetyState

    monkeypatch.setenv("DELTA_UNLOCK_TOKEN", "correct-token")
    s = SafetyState()
    s.kill_all([], actor="test")
    assert s.mode == "HALTED"
    with pytest.raises(SafetyError, match="DENIED"):
        s.unlock("op", "reason", token="wrong-token")
    assert s.mode == "HALTED"  # denial never leaves HALTED
    # Correct token unlocks.
    assert s.unlock("op", "reason", token="correct-token") == "MANUAL"


def test_direct_unlock_no_token_keeps_legacy_behavior(_isolated_session):
    from delta_os.safety import SafetyState

    s = SafetyState()
    s.kill_all([], actor="test")
    assert s.mode == "HALTED"
    # No token passed -> callers enforce (legacy behavior preserved).
    assert s.unlock("op", "reason") == "MANUAL"


def test_board_reflects_kill_activate_deactivate(_isolated_session):
    from governance.kill_switch import KillSwitch
    from risk.kill_switch.kill_switch import KillSwitchBoard

    board = KillSwitchBoard()
    shim = KillSwitch()
    assert not board.any_active()
    shim.bind_to_board(board)
    shim.activate()
    assert board.any_active(), "shim activate must propagate to board GLOBAL"
    assert shim.is_active()
    shim.deactivate()
    assert not board.any_active(), "shim deactivate must clear board GLOBAL"
    assert not shim.is_active()


def test_breaker_reset_without_confirm_refused(_isolated_session):
    from risk.emergency.breaker import BreakerState, CircuitBreaker

    br = CircuitBreaker()
    br.trigger("test halt")
    assert br.get_state() == BreakerState.OPEN
    with pytest.raises(RuntimeError, match="confirm"):
        br.reset()
    assert br.get_state() == BreakerState.OPEN  # no silent resume
    with pytest.raises(RuntimeError, match="confirm"):
        br.close(reason="trying to resume")
    assert br.get_state() == BreakerState.OPEN
    # Explicit confirm works (documented MANUALLY_OVERRIDDEN intermediate).
    br.reset(confirm=True)
    assert br.get_state() == BreakerState.MANUALLY_OVERRIDDEN
    assert not br.is_closed()
    br.close(confirm=True)
    assert br.get_state() == BreakerState.CLOSED


def test_breaker_reset_wrong_token_denied(monkeypatch, _isolated_session):
    from risk.emergency.breaker import BreakerState, CircuitBreaker

    monkeypatch.setenv("DELTA_UNLOCK_TOKEN", "tok-1")
    br = CircuitBreaker()
    br.trigger("test halt")
    with pytest.raises(RuntimeError, match="DENIED"):
        br.reset(confirm=True, token="wrong")
    assert br.get_state() == BreakerState.OPEN
    br.reset(confirm=True, token="tok-1")
    assert br.get_state() == BreakerState.MANUALLY_OVERRIDDEN


def test_halt_marker_round_trips_through_save_restore(monkeypatch, _isolated_session):
    from delta_os import repl as _repl
    from delta_os.safety import SafetyState

    s = SafetyState()
    s.kill_all([], actor="test")
    assert s.mode == "HALTED"

    # Persist via the safety helper, then boot fresh: must boot HALTED.
    from delta_os.safety import persist_safety_mode, read_persisted_safety_mode

    persist_safety_mode("HALTED")
    assert read_persisted_safety_mode() == "HALTED"
    s2 = SafetyState()
    assert s2.mode == "HALTED"

    # Round-trip through the REPL save/restore functions.
    term = _repl.Terminal()
    term.safety.kill_all([], actor="test")
    _repl._save_session(term)
    fresh = _repl.Terminal()  # boot already sees the HALTED marker
    _repl._load_session(fresh)
    assert fresh.safety.mode == "HALTED"


def test_wrong_token_unlock_writes_denial_audit(monkeypatch, _isolated_session):
    from delta_os.safety import SafetyError, SafetyState

    monkeypatch.setenv("DELTA_UNLOCK_TOKEN", "correct-token")
    s = SafetyState()
    s.kill_all([], actor="test")
    assert s.mode == "HALTED"
    with pytest.raises(SafetyError, match="DENIED"):
        s.unlock("op", "reason", token="wrong-token")
    assert s.mode == "HALTED"  # denial never leaves HALTED
    kinds = [r.kind for r in s.compliance._records]
    assert "unlock_denied" in kinds, f"denial must be audit-logged, got {kinds}"
    assert s.compliance.verify()
    assert s.kill.active


def test_bound_board_active_after_safety_kill_all(_isolated_session):
    from delta_os.safety import SafetyState
    from risk.kill_switch.kill_switch import KillSwitchBoard

    board = KillSwitchBoard()
    s = SafetyState()
    assert not board.any_active()
    s.bind_board(board)
    s.kill_all([], actor="test")
    assert s.mode == "HALTED"
    assert board.any_active(), "safety.kill_all must leave bound board GLOBAL active"
    assert s.kill.is_active()


def test_breaker_close_wrong_token_denied(monkeypatch, _isolated_session):
    from risk.emergency.breaker import BreakerState, CircuitBreaker

    monkeypatch.setenv("DELTA_UNLOCK_TOKEN", "tok-1")
    br = CircuitBreaker()
    br.trigger("test halt")
    assert br.get_state() == BreakerState.OPEN
    with pytest.raises(RuntimeError, match="DENIED"):
        br.close(confirm=True, token="wrong")
    assert br.get_state() == BreakerState.OPEN  # refused: no state change
    br.close(confirm=True, token="tok-1")
    assert br.get_state() == BreakerState.CLOSED
    assert br.is_closed()


@pytest.mark.parametrize("garbage", ["not-json{", "123", ""])
def test_persisted_marker_corrupt_returns_none(_isolated_session, garbage):
    import warnings

    from delta_os.safety import read_persisted_safety_mode

    _isolated_session.write_text(garbage, encoding="utf-8")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        assert read_persisted_safety_mode() is None  # corrupt -> None, no raise
