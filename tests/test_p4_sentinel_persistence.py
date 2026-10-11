"""O-item: the watcher survives restarts; duplicates collapse."""
from __future__ import annotations

import json
import sys

sys.path.insert(0, ".")

from delta_os.brain import DeltaBrain, DeltaSentinel
from delta_os.safety import SafetyState


def _sentinel(tmp_path, **kw):
    return DeltaSentinel(
        brain=DeltaBrain.__new__(DeltaBrain),
        safety_state=SafetyState(), equity_fn=lambda: 1000.0,
        positions_fn=lambda: {},
        state_path=str(tmp_path / "sentinel.json"), **kw)


def test_restart_keeps_drawdown_window(tmp_path):
    s = _sentinel(tmp_path)
    s.tick_once()  # peak initialised at 1000
    assert s.peak_equity == 1000.0
    assert (tmp_path / "sentinel.json").exists()

    # Simulated restart: new instance on the same path.
    s2 = _sentinel(tmp_path)
    assert s2.peak_equity == 1000.0, "restart must not reset the peak"
    assert s2.current_equity == 1000.0


def test_breach_after_restart_still_trips(tmp_path):
    s = _sentinel(tmp_path, max_drawdown_pct=2.0)
    s.tick_once()
    s2 = _sentinel(tmp_path, max_drawdown_pct=2.0)
    s2.equity_fn = lambda: 900.0  # -10% vs restored peak
    out = s2.tick_once()
    assert out["halted"] is True
    assert s2.safety.mode == "HALTED"


def test_consecutive_duplicates_collapse(tmp_path):
    s = _sentinel(tmp_path)
    s.equity_fn = lambda: None  # every tick: EQUITY_UNAVAILABLE
    s.tick_once()
    s.tick_once()
    s.tick_once()
    assert len(s.alerts) == 1, s.alerts
    assert s.alerts[0]["duplicates_suppressed"] == 2


def test_corrupt_state_discarded_loudly(tmp_path):
    p = tmp_path / "sentinel.json"
    p.write_text("{not json", encoding="utf-8")
    log = []
    s = DeltaSentinel(
        brain=DeltaBrain.__new__(DeltaBrain),
        safety_state=SafetyState(), equity_fn=lambda: 1000.0,
        positions_fn=lambda: {},
        alert_sink=lambda a: log.append(a),
        state_path=str(p))
    assert s.peak_equity is None
    assert any(a["event"] == "SENTINEL_STATE_UNREADABLE" for a in s.alerts)
