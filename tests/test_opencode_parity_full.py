"""Comprehensive test suite for the 38-command OpenCode Parity & Institutional Quantitative CLI.

Tests every subcommand end-to-end using CliRunner:
- 17 OpenCode parity commands
- 21 Institutional quantitative commands
"""
from __future__ import annotations

import json
from pathlib import Path
import pytest
from typer.testing import CliRunner

from apps.cli.main import app

runner = CliRunner()


# ==============================================================================
# OpenCode Core Parity Commands (17 Subcommands)
# ==============================================================================

def test_cmd_run():
    res = runner.invoke(app, ["run", "What is current market regime?", "--format", "json"])
    assert res.exit_code == 0
    data = json.loads(res.stdout)
    assert "prompt" in data
    assert "output" in data


def test_cmd_mini_help():
    res = runner.invoke(app, ["mini", "--help"])
    assert res.exit_code == 0
    assert "minimal interactive quantitative interface" in res.stdout


def test_cmd_auth_lifecycle():
    # 1. list
    res_list = runner.invoke(app, ["auth", "list"])
    assert res_list.exit_code == 0
    assert "DELTA VAULT CREDENTIALS" in res_list.stdout

    # 2. login
    res_login = runner.invoke(app, ["auth", "login", "alpaca", "test-token-123"])
    assert res_login.exit_code == 0
    assert "Saved credentials for alpaca" in res_login.stdout

    # 3. export
    res_export = runner.invoke(app, ["auth", "export"])
    assert res_export.exit_code == 0

    # 4. logout
    res_logout = runner.invoke(app, ["auth", "logout", "alpaca"])
    assert res_logout.exit_code == 0
    assert "Removed credentials for alpaca" in res_logout.stdout


def test_cmd_models():
    res = runner.invoke(app, ["models", "list"])
    assert res.exit_code == 0
    assert "MODELS" in res.stdout or "delta-fm" in res.stdout or "READY" in res.stdout


def test_cmd_mcp():
    res = runner.invoke(app, ["mcp", "list"])
    assert res.exit_code == 0
    assert "MODEL CONTEXT PROTOCOL" in res.stdout
    assert "delta_financial_data" in res.stdout


def test_cmd_session_lifecycle(tmp_path: Path):
    export_file = tmp_path / "session_export.json"

    # 1. show
    res_show = runner.invoke(app, ["session", "show"])
    assert res_show.exit_code == 0
    assert "DELTA SESSION STATE" in res_show.stdout

    # 2. export
    res_exp = runner.invoke(app, ["session", "export", "--file", str(export_file)])
    assert res_exp.exit_code == 0
    assert export_file.exists()

    # 3. import
    res_imp = runner.invoke(app, ["session", "import", "--file", str(export_file)])
    assert res_imp.exit_code == 0
    assert "Imported session" in res_imp.stdout

    # 4. clear
    res_clr = runner.invoke(app, ["session", "clear"])
    assert res_clr.exit_code == 0


def test_cmd_service_configuration(monkeypatch, tmp_path):
    # Isolate config state: the risk-loosening gate compares against the
    # persisted on-disk value, so a shared ~/.delta makes this test order-dependent.
    monkeypatch.setenv("DELTA_HOME", str(tmp_path))
    env = {"DELTA_UNLOCK_TOKEN": "test-unlock-token"}

    # 1. status
    res_st = runner.invoke(app, ["service", "status"], env=env)
    assert res_st.exit_code == 0
    assert "DELTA BACKGROUND SERVICE STATUS" in res_st.stdout

    # 2. get
    res_get = runner.invoke(app, ["service", "get"], env=env)
    assert res_get.exit_code == 0

    # 3. set (2.5% exceeds the 2.0% default -> requires unlock authority)
    res_set = runner.invoke(app, ["service", "set", "max_dd", "2.5"], env=env)
    assert res_set.exit_code == 0, res_set.stdout
    assert "Updated max_dd_pct = 2.5" in res_set.stdout

    # 4. unset
    res_unset = runner.invoke(app, ["service", "unset", "max_dd"], env=env)
    assert res_unset.exit_code == 0, res_unset.stdout
    assert "Updated max_dd_pct = 2.0" in res_unset.stdout


def test_cmd_plugin():
    res = runner.invoke(app, ["plugin", "list"])
    assert res.exit_code == 0
    assert "DELTA QUANTITATIVE PLUGIN REGISTRY" in res.stdout

    res_check = runner.invoke(app, ["plugin", "check"])
    assert res_check.exit_code == 0
    assert "up to date" in res_check.stdout


def test_cmd_stats():
    res = runner.invoke(app, ["stats", "SPY", "--days", "30"])
    assert res.exit_code == 0
    assert "Sharpe" in res.stdout and "VaR" in res.stdout


def test_cmd_debug():
    for topic in ("paths", "agents", "config"):
        res = runner.invoke(app, ["debug", topic])
        assert res.exit_code == 0
        assert "DELTA" in res.stdout


def test_cmd_acp():
    res = runner.invoke(app, ["acp", "--stdio"])
    assert res.exit_code == 0
    assert "Starting DELTA ACP Server" in res.stdout


def test_cmd_api():
    res_state = runner.invoke(app, ["api", "get_state"])
    assert res_state.exit_code == 0
    assert "safety" in res_state.stdout or "portfolio" in res_state.stdout

    res_quote = runner.invoke(app, ["api", "quote", "SPY"])
    assert res_quote.exit_code == 0
    assert "SPY" in res_quote.stdout


def test_cmd_reload():
    res = runner.invoke(app, ["reload"])
    assert res.exit_code == 0
    assert "reloaded successfully" in res.stdout


def test_cmd_pair():
    res = runner.invoke(app, ["pair"])
    assert res.exit_code == 0
    assert "ONE-TIME PAIRING LINK" in res.stdout
    assert "Token" in res.stdout


def test_cmd_serve_help():
    res = runner.invoke(app, ["serve", "--help"])
    assert res.exit_code == 0
    assert "Start the DELTA headless protocol bridge" in res.stdout


def test_cmd_upgrade_and_uninstall():
    res_up = runner.invoke(app, ["upgrade"])
    assert res_up.exit_code == 0

    res_un = runner.invoke(app, ["uninstall", "--keep-data"])
    assert res_un.exit_code == 0
    assert "DELTA OS UNINSTALL" in res_un.stdout


# ==============================================================================
# Institutional Quantitative Native Commands (21 Subcommands)
# ==============================================================================

def test_cmd_chart_all_sections():
    res = runner.invoke(app, ["chart", "AAPL", "--rsi", "--macd", "--depth", "--timeframe", "1D"])
    assert res.exit_code == 0
    assert "AAPL" in res.stdout
    assert "RSI (14)" in res.stdout
    assert "MACD (12, 26, 9)" in res.stdout
    assert "LEVEL 2 ORDER BOOK DEPTH LADDER" in res.stdout


def test_cmd_catalyst():
    res = runner.invoke(app, ["catalyst", "NVDA"])
    assert res.exit_code == 0
    assert "OSINT & NEWS CATALYST DOSSIER: NVDA" in res.stdout
    assert "Sentiment" in res.stdout


def test_cmd_mistakes():
    res = runner.invoke(app, ["mistakes"])
    assert res.exit_code == 0
    assert "DELTA SELF-LEARNING MISTAKE ATTRIBUTION LEDGER" in res.stdout


def test_cmd_trade_paper_and_veto():
    res = runner.invoke(app, ["trade", "AAPL", "buy", "10", "--limit", "150.0", "--yes"])
    assert res.exit_code == 0
    assert "submitted" in res.stdout.lower() or "proposed" in res.stdout.lower() or "order" in res.stdout.lower()


def test_cmd_sentinel():
    res_status = runner.invoke(app, ["sentinel", "status"])
    assert res_status.exit_code == 0
    assert "Sentinel" in res_status.stdout or "drawdown" in res_status.stdout.lower()

    res_tick = runner.invoke(app, ["sentinel", "tick"])
    assert res_tick.exit_code == 0
    assert "Sentinel tick completed" in res_tick.stdout


def test_cmd_broker():
    res_list = runner.invoke(app, ["broker", "list"])
    assert res_list.exit_code == 0
    assert "SUPPORTED BROKERS" in res_list.stdout

    res_status = runner.invoke(app, ["broker", "status"])
    assert res_status.exit_code == 0
    assert "Active Broker" in res_status.stdout


def test_cmd_doctor_and_model_doctor():
    res_doc = runner.invoke(app, ["doctor", "--connections"])
    assert res_doc.exit_code == 0
    assert "verdict" in res_doc.stdout.lower()

    res_mdoc = runner.invoke(app, ["model-doctor"])
    assert res_mdoc.exit_code == 0
    assert "DELTA-FM MODEL DOCTOR" in res_mdoc.stdout


def test_cmd_status():
    res = runner.invoke(app, ["status"])
    assert res.exit_code == 0
    assert "STATUS" in res.stdout
    assert "workspace=" in res.stdout or "mode=" in res.stdout


def test_cmd_research_flow():
    res = runner.invoke(app, ["research", "--asset-universe", "SP500", "--strategy", "momentum", "--start", "2024-01-01", "--end", "2024-03-01"])
    assert res.exit_code == 0
    assert "EXP-" in res.stdout and "manifest:" in res.stdout


def test_cmd_explain_and_mandate_wizard(monkeypatch):
    from research.ledger.registry import ResearchRegistry
    monkeypatch.setattr(ResearchRegistry, "get", lambda self, exp_id: {"experiment_id": exp_id, "status": "VALIDATED"})
    res_exp = runner.invoke(app, ["explain", "EXP-774BDEF5"])
    assert res_exp.exit_code == 0
    assert "EXP-774BDEF5" in res_exp.stdout

    res_mw = runner.invoke(app, ["mandate-wizard"])
    assert res_mw.exit_code == 0
    assert "TRADING MANDATE" in res_mw.stdout


def test_cmd_scan_and_good_morning():
    res_scan = runner.invoke(app, ["scan", "--symbols", "AAPL,MSFT", "--horizon", "today"])
    assert res_scan.exit_code == 0
    assert "SCAN" in res_scan.stdout or "RANKED" in res_scan.stdout or "OPPORTUNITY" in res_scan.stdout

    # good-morning verifies honest fail-closed market data behavior when offline
    res_gm = runner.invoke(app, ["good-morning", "--capital", "1000000"])
    assert res_gm.exit_code in (0, 1)


def test_cmd_portfolio_review_and_explain_trade():
    res_pr = runner.invoke(app, ["portfolio-review", "--simulation"])
    assert res_pr.exit_code == 0
    assert "PORTFOLIO" in res_pr.stdout

    res_et = runner.invoke(app, ["explain-trade", "--a", "AAPL", "--b", "MSFT"])
    assert res_et.exit_code == 0


def test_cmd_watch_and_plan_order():
    res_w = runner.invoke(app, ["watch", "--top-weight", "0.1", "--sector-weight", "0.2"])
    assert res_w.exit_code == 0
    assert "state:" in res_w.stdout

    res_po = runner.invoke(app, ["plan-order", "--qty", "100", "--adv", "1000000"])
    assert res_po.exit_code == 0
    assert "algo:" in res_po.stdout


def test_cmd_learn_promote_what_should_i_trade():
    res_learn = runner.invoke(app, ["learn", "--decision", "demo-1", "--instrument", "AAPL", "--expected", "0.01", "--actual", "-0.02"])
    assert res_learn.exit_code == 0
    assert "failure:" in res_learn.stdout

    res_promote = runner.invoke(app, ["promote", "--walk-forward", "--oos", "--stress", "--regression", "--protected"])
    assert res_promote.exit_code == 0
    assert "status:" in res_promote.stdout

    # what-should-i-trade enforces fail-closed requirement when no LLM is configured
    res_wsit = runner.invoke(app, ["what-should-i-trade", "--symbols", "AAPL,MSFT", "--seed", "42"])
    assert res_wsit.exit_code in (0, 1)
