"""P0: Sentinel loss-wire contract. Fail-closed, no silent swallows, live data only."""
import time

import pytest

from delta_os.brain import DeltaBrain, DeltaSentinel
from delta_os.safety import SafetyState


def _safety():
    return SafetyState()


def test_drawdown_breach_freezes_engine_with_receipt():
    brain = DeltaBrain.__new__(DeltaBrain)  # no router needed for this path
    s = _safety()
    eq = {"v": 100_000.0}
    sent = DeltaSentinel(
        brain=brain, safety_state=s,
        equity_fn=lambda: eq["v"],
        positions_fn=lambda: {"SPY": 10.0},
        max_drawdown_pct=2.0, check_interval_s=3600.0,
    )
    sent.start()
    try:
        sent.tick_once()  # sets peak=100k
        eq["v"] = 97_000.0  # -3% breach
        sent.tick_once()
        assert s.mode == "HALTED"
        assert s.kill.active
        kinds = [a["event"] for a in sent.alerts]
        assert "AUTOMATED_KILL_SWITCH_TRIPPED" in kinds
    finally:
        sent.stop()


def test_no_equity_source_means_monitor_only_never_halt():
    brain = DeltaBrain.__new__(DeltaBrain)
    s = _safety()
    sent = DeltaSentinel(
        brain=brain, safety_state=s,
        equity_fn=lambda: None,  # UNAVAILABLE ledger
        positions_fn=lambda: {},
        max_drawdown_pct=2.0, check_interval_s=3600.0,
    )
    sent.start()
    try:
        sent.tick_once()
        assert s.mode != "HALTED"
        assert any(a["event"] == "EQUITY_UNAVAILABLE" for a in sent.alerts)
    finally:
        sent.stop()


def test_heartbeat_present_and_stale_when_stopped():
    brain = DeltaBrain.__new__(DeltaBrain)
    s = _safety()
    sent = DeltaSentinel(
        brain=brain, safety_state=s,
        equity_fn=lambda: 50_000.0, positions_fn=lambda: {},
        check_interval_s=3600.0,
    )
    st = sent.status()
    assert "last_tick_utc" in st and "equity_source" in st
    sent.start()
    try:
        sent.tick_once()
        assert sent.status()["last_tick_utc"] is not None
    finally:
        sent.stop()


def test_no_demo_positions_anywhere():
    import inspect

    from delta_os import brain as bmod
    src = inspect.getsource(bmod.DeltaSentinel)
    assert "NVDA" not in src and "1_000_000" not in src and "1000000" not in src.replace("_", "")


def test_loop_errors_surface_not_swallowed():
    brain = DeltaBrain.__new__(DeltaBrain)
    s = _safety()
    calls = {"n": 0}

    def bad_equity():
        calls["n"] += 1
        raise RuntimeError("ledger exploded")

    sent = DeltaSentinel(
        brain=brain, safety_state=s,
        equity_fn=bad_equity, positions_fn=lambda: {},
        check_interval_s=3600.0,
    )
    sent.start()
    try:
        with pytest.raises(RuntimeError):
            sent.tick_once()
        assert s.mode != "HALTED"
    finally:
        sent.stop()
