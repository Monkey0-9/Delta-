"""Tests for P0-C: Configuration integrity, validation, hot-reload, risk authorization,
and daemon PID reuse, readiness, heartbeats, and restart.
"""
from __future__ import annotations

import json
import os
import signal
import sys
import time
from pathlib import Path

import pytest

from delta_os import daemon_service as ds
from delta_os import service_config as sc


@pytest.fixture
def clean_delta_home(tmp_path, monkeypatch):
    """Isolate DELTA_HOME to a temporary directory."""
    monkeypatch.setenv("DELTA_HOME", str(tmp_path))
    monkeypatch.delenv("DELTA_UNLOCK_TOKEN", raising=False)
    return tmp_path


def test_config_corruption_fails_closed(clean_delta_home):
    """Corrupt config file must raise ConfigurationCorruptError, not silently return defaults."""
    cfg_path = clean_delta_home / "service_config.json"
    cfg_path.write_text("{this is not valid json!}", encoding="utf-8")

    with pytest.raises(sc.ConfigurationCorruptError) as exc_info:
        sc.load_config()
    assert "Corrupt" in str(exc_info.value) or "JSON" in str(exc_info.value)


def test_config_invalid_schema_fails_closed(clean_delta_home):
    """Config with invalid non-numeric or out-of-bounds values must be rejected."""
    cfg_path = clean_delta_home / "service_config.json"
    cfg_path.write_text(json.dumps({"max_dd_pct": "not-a-number"}), encoding="utf-8")

    with pytest.raises(sc.ConfigurationCorruptError):
        sc.load_config()


def test_risk_loosening_requires_authorization(clean_delta_home, monkeypatch):
    """Increasing max_dd_pct is risk-loosening and must require DELTA_UNLOCK_TOKEN."""
    # Baseline default is 2.0
    # Attempt to loosen without token -> REJECTED
    ok, msg, _ = sc.set_value("max_dd_pct", 5.0)
    assert not ok
    assert "Authorization required" in msg or "permission" in msg.lower() or "auth" in msg.lower()

    # Attempt to loosen with correct token -> ALLOWED
    monkeypatch.setenv("DELTA_UNLOCK_TOKEN", "SECRET_RISK_KEY_123")
    ok, msg, cfg = sc.set_value("max_dd_pct", 5.0, auth_token="SECRET_RISK_KEY_123")
    assert ok
    assert cfg["max_dd_pct"] == 5.0

    # Tightening risk (5.0 -> 1.5) does not loosen risk and should succeed even without token
    monkeypatch.delenv("DELTA_UNLOCK_TOKEN", raising=False)
    ok, msg, cfg = sc.set_value("max_dd_pct", 1.5)
    assert ok
    assert cfg["max_dd_pct"] == 1.5


def test_config_revision_and_restart_required(clean_delta_home):
    """Restart-required keys must be flagged as RESTART_REQUIRED; hot-reloadable keys update revision."""
    ok, msg, cfg = sc.set_value("interval_s", 5.0)
    assert ok
    assert cfg["revision"] >= 2
    assert "RESTART_REQUIRED" not in msg

    # Changing equity_source requires restart
    ok, msg, cfg = sc.set_value("equity_source", "broker_live")
    assert ok
    assert "RESTART_REQUIRED" in msg
    assert cfg["revision"] >= 3


def test_daemon_pid_reuse_detected_and_cleared(clean_delta_home):
    """If daemon.pid points to an existing non-Delta process (e.g. init PID 1), it must be detected as stale."""
    pid_file, _ = ds.get_daemon_paths()
    # PID 1 is systemd/init on linux, always running but definitely not python delta_os.daemon_service
    pid_file.write_text("1", encoding="utf-8")

    running, pid = ds.is_daemon_running()
    assert not running
    assert pid is None
    # Stale pid file should have been cleaned up
    assert not pid_file.exists()


def test_daemon_lifecycle_heartbeat_and_readiness(clean_delta_home):
    """Verify daemon start creates readiness and heartbeat, and stop cleanly shuts down."""
    # Start daemon
    res = ds.start_daemon(max_dd=2.0, interval_s=0.5)
    try:
        assert res["status"] == "STARTED"
        pid = res["pid"]
        assert pid is not None

        # Duplicate start must be rejected
        dup = ds.start_daemon(max_dd=2.0, interval_s=0.5)
        assert dup["status"] == "ALREADY_RUNNING"
        assert dup["pid"] == pid

        # Check readiness / heartbeat
        d_dir = clean_delta_home
        heartbeat_file = d_dir / "daemon_heartbeat.json"
        
        # Wait up to 3 seconds for heartbeat
        for _ in range(30):
            if heartbeat_file.exists():
                break
            time.sleep(0.1)
        
        assert heartbeat_file.exists()
        hb = json.loads(heartbeat_file.read_text(encoding="utf-8"))
        assert hb["pid"] == pid
        assert hb["status"] in ("HEALTHY", "RUNNING", "READY")

        # Test restart_daemon
        res_rst = ds.restart_daemon(max_dd=2.0, interval_s=0.5)
        assert res_rst["status"] == "STARTED"
        new_pid = res_rst["pid"]
        assert new_pid != pid

    finally:
        ds.stop_daemon()
        running, _ = ds.is_daemon_running()
        assert not running
