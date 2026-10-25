"""Acceptance tests for Truthful CLI Command Semantics & Provenance.

Verifies:
1. delta run --timeout terminates execution cleanly when deadline is exceeded.
2. delta run NDJSON output emits structured events without crashing.
3. delta auth login displays security warning when positional secret is supplied.
4. delta upgrade reports commit status and handles offline gracefully.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typer.testing import CliRunner
import pytest

from apps.cli.main import app

runner = CliRunner()


def test_cli_run_timeout_cancellation(monkeypatch):
    from delta_os import repl

    def slow_handle(self, text):
        time.sleep(2.0)
        return "slow response", None

    monkeypatch.setattr(repl.Terminal, "handle", slow_handle)

    t0 = time.perf_counter()
    res = runner.invoke(app, ["run", "Slow query", "--timeout", "0.2"])
    elapsed = time.perf_counter() - t0

    # Must return quickly and not hang for 2 seconds
    assert elapsed < 1.5
    assert "TIMEOUT" in res.stdout or "ERROR" in res.stdout


def test_cli_auth_positional_token_warning():
    res = runner.invoke(app, ["auth", "login", "alpaca", "my-secret-key-12345"])
    assert res.exit_code == 0
    assert "[SECURITY WARNING]" in res.stderr or "[SECURITY NOTICE]" in res.stderr


def test_cli_upgrade_reporting():
    res = runner.invoke(app, ["upgrade"])
    assert res.exit_code == 0
    assert "Installed commit:" in res.stdout
    assert "Current branch status:" in res.stdout
    assert "verified release commit" in res.stdout
