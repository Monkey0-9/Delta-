"""Tests for OpenCode Advanced Parity: file context, timeouts, NDJSON, session redaction/fork/switch, shell completion, institutional doctor, and NCM MCP tool.
"""
from __future__ import annotations

import json
from pathlib import Path
from typer.testing import CliRunner

from apps.cli.main import app

runner = CliRunner()


def test_cmd_run_ndjson_streaming():
    res = runner.invoke(app, ["run", "What is current market regime?", "--format", "ndjson"])
    assert res.exit_code == 0
    lines = [line.strip() for line in res.stdout.strip().split("\n") if line.strip()]
    assert len(lines) >= 3

    start_event = json.loads(lines[0])
    assert start_event["event"] == "start"
    assert "model" in start_event

    done_event = json.loads(lines[-1])
    assert done_event["event"] == "done"
    assert "latency_ms" in done_event
    assert "provenance" in done_event


def test_cmd_run_stats_flag():
    res = runner.invoke(app, ["run", "Explain margin safety", "--stats"])
    assert res.exit_code == 0
    assert "[STATS]" in res.stdout
    assert "latency:" in res.stdout
    assert "model:" in res.stdout
    assert "provenance:" in res.stdout


def test_cmd_run_with_file_context(tmp_path: Path):
    f = tmp_path / "research_notes.txt"
    f.write_text("Asset: TSLA. Note: High implied volatility skew detected before earnings.")

    res = runner.invoke(app, ["run", "Analyze the note", "--file", str(f), "--stats"])
    assert res.exit_code == 0
    assert "[STATS]" in res.stdout


def test_cmd_session_export_redacts_secrets(tmp_path: Path):
    # Save a dummy session with sensitive keys
    from delta_os import safety
    p = safety._session_path()
    dummy = {
        "workspace": "TEST-VAULT",
        "theme": "monokai",
        "api_key": "sk-live-1234567890",
        "auth_token": "secret-token-xyz",
        "password": "super-secure-pass",
    }
    p.write_text(json.dumps(dummy), encoding="utf-8")

    res = runner.invoke(app, ["session", "export"])
    assert res.exit_code == 0
    data = json.loads(res.stdout)
    assert data["api_key"] == "[REDACTED]"
    assert data["auth_token"] == "[REDACTED]"
    assert data["password"] == "[REDACTED]"
    assert data["workspace"] == "TEST-VAULT"


def test_cmd_session_fork_and_switch():
    # 1. Fork
    fork_name = "test-fork-algo-99"
    res_fork = runner.invoke(app, ["session", "fork", fork_name])
    assert res_fork.exit_code == 0
    assert f"Forked session into '{fork_name}'" in res_fork.stdout

    # 2. List
    res_list = runner.invoke(app, ["session", "list"])
    assert res_list.exit_code == 0
    assert fork_name in res_list.stdout

    # 3. Switch back to default
    res_switch = runner.invoke(app, ["session", "switch", fork_name])
    assert res_switch.exit_code == 0
    assert f"Resumed session '{fork_name}'" in res_switch.stdout


def test_cmd_shell_completion():
    res_bash = runner.invoke(app, ["completion", "bash"])
    assert res_bash.exit_code == 0
    assert "_DELTA_COMPLETE=bash_source" in res_bash.stdout

    res_zsh = runner.invoke(app, ["completion", "zsh"])
    assert res_zsh.exit_code == 0
    assert "_DELTA_COMPLETE=zsh_source" in res_zsh.stdout

    res_fish = runner.invoke(app, ["completion", "fish"])
    assert res_fish.exit_code == 0
    assert "_DELTA_COMPLETE=fish_source" in res_fish.stdout


def test_cmd_doctor_institutional_audit():
    res = runner.invoke(app, ["doctor", "--institutional"])
    assert res.exit_code == 0
    assert "INSTITUTIONAL QUANTITATIVE AUDIT & READINESS REPORT" in res.stdout
    assert "1. Native C-ABI Kernel" in res.stdout
    assert "Backend: RUST" in res.stdout
    assert "2. Temporal PIT Data" in res.stdout
    assert "3. Canonical OMS Journal" in res.stdout
    assert "VERDICT: GO-PAPER / INSTITUTIONAL_AUDIT_PASS" in res.stdout


def test_ncm_mcp_trajectory_tool():
    from tools.delta_mcp import _call, _tools_spec
    specs = {t["name"]: t for t in _tools_spec()}
    assert "delta_ncm_trajectory" in specs
    assert "symbol" in specs["delta_ncm_trajectory"]["inputSchema"]["required"]

    result = _call("delta_ncm_trajectory", {
        "symbol": "SPY",
        "macro_context": "Tightening liquidity conditions and yield curve inversion",
        "horizon": 3,
    })
    assert result["domain"] == "next-concept-modeling"
    assert result["symbol"] == "SPY"
    assert result["execution_eligibility"] is False
    assert result["hardware_acceleration"] in ("rust", "numpy")
    assert len(result["trajectory"]) == 3
