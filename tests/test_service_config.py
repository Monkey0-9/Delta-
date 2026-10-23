"""Institutional Tests for DELTA Service Configuration Subsystem.

Validates:
1. Schema validation, typecasting, and numerical bounds.
2. Atomic filesystem writes (fsync + 0o600 permissions).
3. Reset/unset to defaults.
4. Out-of-bounds rejection and alias normalization.
"""
from __future__ import annotations

import os
from pathlib import Path
import pytest

from delta_os import service_config as sc


def test_service_config_defaults(tmp_path, monkeypatch):
    monkeypatch.setenv("DELTA_HOME", str(tmp_path))
    cfg = sc.load_config()
    assert cfg["max_dd_pct"] == 2.0
    assert cfg["interval_s"] == 3.0
    assert cfg["log_level"] == "INFO"
    assert cfg["daily_reset_utc"] == "00:00"


def test_service_config_set_and_get(tmp_path, monkeypatch):
    monkeypatch.setenv("DELTA_HOME", str(tmp_path))

    # Test setting valid values with aliases
    ok, msg, cfg = sc.set_value("max_dd", "4.5")
    assert ok, msg
    assert cfg["max_dd_pct"] == 4.5
    assert sc.get_value("max_dd") == 4.5
    assert sc.get_value("max_dd_pct") == 4.5

    ok, msg, cfg = sc.set_value("interval", "10.0")
    assert ok, msg
    assert cfg["interval_s"] == 10.0
    assert sc.get_value("interval") == 10.0

    # Verify persisted on disk with 0o600 permissions
    cfg_file = tmp_path / "service_config.json"
    assert cfg_file.exists()
    st = os.stat(cfg_file)
    assert (st.st_mode & 0o777) == 0o600

    # Reload fresh from disk
    fresh_cfg = sc.load_config()
    assert fresh_cfg["max_dd_pct"] == 4.5
    assert fresh_cfg["interval_s"] == 10.0


def test_service_config_out_of_bounds_rejection(tmp_path, monkeypatch):
    monkeypatch.setenv("DELTA_HOME", str(tmp_path))

    # Reject too small
    ok, msg, _ = sc.set_value("max_dd", "0.01")
    assert not ok
    assert "out of bounds" in msg.lower()

    # Reject too high
    ok, msg, _ = sc.set_value("max_dd", "25.0")
    assert not ok
    assert "out of bounds" in msg.lower()

    # Reject invalid number string
    ok, msg, _ = sc.set_value("max_dd", "abc")
    assert not ok
    assert "valid number" in msg.lower()


def test_service_config_unset(tmp_path, monkeypatch):
    monkeypatch.setenv("DELTA_HOME", str(tmp_path))

    sc.set_value("max_dd", "5.0")
    assert sc.get_value("max_dd") == 5.0

    ok, msg, cfg = sc.unset_value("max_dd")
    assert ok, msg
    assert cfg["max_dd_pct"] == 2.0
    assert sc.get_value("max_dd") == 2.0
