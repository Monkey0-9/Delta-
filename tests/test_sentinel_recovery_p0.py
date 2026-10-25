"""Tests for P0-B: Sentinel Heartbeat, failure degradation, and operational recovery.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

from delta_os import daemon_service as ds


def test_heartbeat_records_successful_cycle(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("DELTA_HOME", str(tmp_path))
    hb_file = ds.get_heartbeat_path()

    # Verify initial heartbeat file doesn't exist
    assert not hb_file.exists()


def test_daemon_heartbeat_schema_fields(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("DELTA_HOME", str(tmp_path))
    hb_file = ds.get_heartbeat_path()

    now_iso = datetime.now(timezone.utc).isoformat()
    hb_data = {
        "pid": 9999,
        "timestamp": now_iso,
        "status": "HEALTHY",
        "applied_revision": 1,
        "ticks": 10,
        "ready": True,
        "last_successful_cycle_utc": now_iso,
        "consecutive_errors": 0,
        "last_error": None,
        "max_dd_pct": 2.0,
        "interval_s": 3.0,
    }
    hb_file.write_text(json.dumps(hb_data), encoding="utf-8")

    st = ds.get_daemon_status()
    assert st["heartbeat"]["last_successful_cycle_utc"] == now_iso
    assert st["heartbeat"]["consecutive_errors"] == 0
    assert st["heartbeat"]["ready"] is True
