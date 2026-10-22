"""Acceptance tests for Unified DELTA CLI (OpenCode Parity)."""
from __future__ import annotations

import json
import pytest
from typer.testing import CliRunner
from apps.cli.main import app

runner = CliRunner()


def test_cli_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "DELTA Finance-Native Autonomous Intelligence" in result.stdout
    assert "chart" in result.stdout
    assert "auth" in result.stdout
    assert "models" in result.stdout
    assert "mcp" in result.stdout
    assert "session" in result.stdout
    assert "sentinel" in result.stdout
    assert "broker" in result.stdout
    assert "stats" in result.stdout
    assert "catalyst" in result.stdout


def test_cli_auth_list():
    result = runner.invoke(app, ["auth", "list"])
    assert result.exit_code == 0
    assert "DELTA VAULT CREDENTIALS" in result.stdout
    assert "alpaca" in result.stdout
    assert "openai" in result.stdout


def test_cli_models_list():
    result = runner.invoke(app, ["models", "list"])
    assert result.exit_code == 0
    assert "DELTA MODEL REGISTRY" in result.stdout
    assert "delta-fm-research" in result.stdout
    assert "READY" in result.stdout


def test_cli_mcp_list():
    result = runner.invoke(app, ["mcp", "list"])
    assert result.exit_code == 0
    assert "DELTA MODEL CONTEXT PROTOCOL" in result.stdout
    assert "delta_financial_data" in result.stdout


def test_cli_session_show():
    result = runner.invoke(app, ["session", "show"])
    assert result.exit_code == 0
    assert "DELTA SESSION STATE" in result.stdout
    assert "Workspace" in result.stdout


def test_cli_sentinel_status():
    result = runner.invoke(app, ["sentinel", "status"])
    assert result.exit_code == 0
    assert "DELTA 24/7 AUTONOMOUS SENTINEL" in result.stdout
    assert "Engine State" in result.stdout


def test_cli_broker_list_and_status():
    res_list = runner.invoke(app, ["broker", "list"])
    assert res_list.exit_code == 0
    assert "paper" in res_list.stdout

    res_stat = runner.invoke(app, ["broker", "status"])
    assert res_stat.exit_code == 0
    assert "Active Broker" in res_stat.stdout


def test_cli_chart():
    result = runner.invoke(app, ["chart", "AAPL", "--days", "20"])
    assert result.exit_code == 0
    assert "AAPL" in result.stdout
    assert "ORDER BOOK DEPTH LADDER" in result.stdout


def test_cli_catalyst():
    result = runner.invoke(app, ["catalyst", "NVDA"])
    assert result.exit_code == 0
    assert "NVDA" in result.stdout
    assert "OSINT & NEWS CATALYST DOSSIER" in result.stdout


def test_cli_run_headless_json():
    result = runner.invoke(app, ["run", "What is the price of NVDA?", "--format", "json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["model"] == "delta-fm-research"
    assert "output" in data
