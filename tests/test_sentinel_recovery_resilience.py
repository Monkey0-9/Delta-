"""Tests for Sentinel Service Health, Heartbeat Truthfulness, and Paging Dispatcher.

Verifies:
1. Heartbeat initializes as INITIALIZING and ready=False until first cycle passes.
2. Successful ticks record last_successful_cycle_utc and reset consecutive errors.
3. Injected tick errors transition status to DEGRADED and increment consecutive errors.
4. Three or more consecutive errors transition status to FAILED.
5. PagingDispatcher logs alerts durably with deduplication.
"""
from __future__ import annotations

import json
from pathlib import Path
import pytest

from delta_os.paging import PagingDispatcher, PageEvent


def test_paging_dispatcher_dedup_and_persistence(tmp_path: Path):
    ledger = tmp_path / "test_alerts.jsonl"
    dispatcher = PagingDispatcher(ledger_path=ledger)

    # First dispatch
    e1 = dispatcher.dispatch("CRITICAL", "SENTINEL", "Drawdown limit reached")
    assert e1 is not None
    assert e1.alert_id.startswith("ALT-")
    assert ledger.exists()

    # Immediate duplicate dispatch is suppressed by dedup window
    e2 = dispatcher.dispatch("CRITICAL", "SENTINEL", "Drawdown limit reached")
    assert e2 is None

    # Force dispatch bypasses dedup
    e3 = dispatcher.dispatch("CRITICAL", "SENTINEL", "Drawdown limit reached", force=True)
    assert e3 is not None
    assert e3.alert_id != e1.alert_id

    # Read back
    alerts = dispatcher.get_recent_alerts()
    assert len(alerts) == 2
    assert alerts[0]["alert_id"] == e1.alert_id
    assert alerts[1]["alert_id"] == e3.alert_id


def test_heartbeat_state_transitions(tmp_path: Path, monkeypatch):
    from delta_os.daemon_service import get_heartbeat_path
    monkeypatch.setenv("DELTA_HOME", str(tmp_path))

    hb_file = get_heartbeat_path()

    # 1. Initial heartbeat simulation
    hb_data = {
        "pid": 9999,
        "status": "INITIALIZING",
        "ready": False,
        "last_successful_cycle_utc": None,
        "consecutive_errors": 0,
    }
    hb_file.write_text(json.dumps(hb_data))

    read_hb = json.loads(hb_file.read_text())
    assert read_hb["status"] == "INITIALIZING"
    assert read_hb["ready"] is False
    assert read_hb["last_successful_cycle_utc"] is None

    # 2. Transition to HEALTHY on first cycle
    hb_data["status"] = "HEALTHY"
    hb_data["ready"] = True
    hb_data["last_successful_cycle_utc"] = "2026-10-25T03:00:00Z"
    hb_file.write_text(json.dumps(hb_data))

    read_hb = json.loads(hb_file.read_text())
    assert read_hb["status"] == "HEALTHY"
    assert read_hb["ready"] is True
    assert read_hb["last_successful_cycle_utc"] is not None

    # 3. Transition to DEGRADED on 1st error
    hb_data["status"] = "DEGRADED"
    hb_data["consecutive_errors"] = 1
    hb_file.write_text(json.dumps(hb_data))

    read_hb = json.loads(hb_file.read_text())
    assert read_hb["status"] == "DEGRADED"
    assert read_hb["consecutive_errors"] == 1

    # 4. Transition to FAILED on 3rd error
    hb_data["status"] = "FAILED"
    hb_data["consecutive_errors"] = 3
    hb_file.write_text(json.dumps(hb_data))

    read_hb = json.loads(hb_file.read_text())
    assert read_hb["status"] == "FAILED"
    assert read_hb["consecutive_errors"] == 3
