"""Comprehensive test suite for institutional OpenCode-grade CLI design and specifications."""
from __future__ import annotations

import pytest
from delta_tui.app import DeltaApp
from delta_tui.commands.palette import format_palette_box
from delta_tui.widgets.chrome import format_quant_num, header_text, footer_text
from trader.opencode_terminal import OpenCodeTerminal
from apps.cli.delta import ExistingSystemBackend


def test_state_a_landing_minimal():
    app = DeltaApp()
    rendered = app.render_current()
    # State A header
    assert "DELTA" in rendered
    assert "QUANT INTELLIGENCE CLI" in rendered
    assert "MARKET" in rendered
    assert "DATA" in rendered
    assert "RISK" in rendered
    assert "PAPER" in rendered
    # State A exact frontpart elements
    assert "RESEARCH  |  SIMULATE  |  ANALYZE  |  EXECUTE  |  LEARN" in rendered
    assert "Ask DELTA anything, run a strategy, analyze a market, or type / for commands..." in rendered
    assert "Ctrl + K" in rendered
    assert "Model: delta-fm-research" in rendered
    assert "Agent: quant-researcher" in rendered
    assert "Session: default" in rendered
    # Zero technical noise
    assert "Python" not in rendered
    assert "CUDA" not in rendered
    assert "RAM" not in rendered


def test_state_b_active_conversation():
    app = DeltaApp()
    # Turn 1: user asks a question
    resp = app.dispatch("Analyze NVDA's current regime.")
    assert resp is not None
    # Now in State B: conversation dominant
    rendered = app.render_current()
    assert "You" in rendered
    assert "Analyze NVDA's current regime." in rendered
    assert "DELTA" in rendered
    assert "Model delta-fm-research · Agent quant-researcher" in rendered
    assert "> _" in rendered


def test_kill_switch_institutional_box():
    app = DeltaApp()
    # Armed step
    armed = app.dispatch("/kill")
    assert "KILL SWITCH ARMED" in armed

    # Confirmed step
    halted = app.dispatch("/kill CONFIRM")
    assert "EXECUTION HALTED" in halted
    assert "Kill switch activated" in halted
    assert "New orders       BLOCKED" in halted
    assert "Existing orders CANCEL REQUESTED" in halted
    assert "Agents           RESTRICTED" in halted
    assert "Research         AVAILABLE" in halted
    assert "[Review state] [Resume authorization]" in halted
    assert app.store.risk_state == "BLOCKED"


def test_command_palette_categorization():
    box = format_palette_box("")
    assert "Search commands..." in box
    assert "/research" in box
    assert "/market" in box
    assert "/portfolio" in box
    assert "/risk" in box
    assert "/simulate" in box
    assert "/backtest" in box
    assert "/trade" in box
    assert "/automation" in box
    assert "/finance-chat" in box
    assert "/finance-agent" in box
    assert "/kill-switch" in box
    assert "System/AI:" in box
    assert "/model" in box
    assert "/agent" in box


def test_finance_chat_vs_finance_agent():
    app = DeltaApp()
    chat_out = app.dispatch("/finance-chat Explain Treasury yields impact on factor risk")
    assert chat_out is not None

    agent_out = app.dispatch("/finance-agent NVDA factor exposure")
    # Truth rule: no fake scripted confidence/regime. Real backend error or UNAVAILABLE.
    assert ("DELTA LLM ERROR" in agent_out or
            "finance-agent UNAVAILABLE" in agent_out or
            "Analyzing NVDA factor exposure..." in agent_out)


def test_automation_mental_model():
    app = DeltaApp()
    auto_out = app.dispatch("/automation")
    assert "AUTOMATIONS" in auto_out
    assert "Morning portfolio review" in auto_out
    assert "Risk regime watch" in auto_out
    assert "research monitor" in auto_out
    assert "[Create] [Pause] [Resume] [History]" in auto_out


def test_research_persistent_state():
    app = DeltaApp()
    res_out = app.dispatch("/research")
    assert "RESEARCH" in res_out
    assert "H-2026-0041" in res_out
    assert "EXP-9182" in res_out
    assert "momentum-v4" in res_out
    assert "OOS validation" in res_out
    assert "[Open analysis ↗] [Run research] [Simulate]" in res_out


def test_browser_handoff_and_open():
    app = DeltaApp()
    open_out = app.dispatch("/open")
    assert "Browser workspace" in open_out
    assert "delta://" in open_out
    # Truth rule: DELTA Web is NOT IMPLEMENTED — do not claim it opened.
    assert "DELTA Web is NOT IMPLEMENTED" in open_out
    assert "provenance: UNAVAILABLE" in open_out


def test_quant_numerical_formatting():
    assert format_quant_num(12_431_221.24, kind="currency") == "$12.43M"
    assert format_quant_num(4_820_000.0, kind="currency") == "$4.82M"
    assert format_quant_num(850_000.0, kind="currency") == "$850.00K"
    assert format_quant_num(2.41, kind="percent") == "+2.41%"
    assert format_quant_num(-12.4, kind="percent") == "-12.40%"
    assert format_quant_num(1.28, kind="ratio") == "1.28×"
    assert format_quant_num(18.2, kind="bps") == "18.2 bps"
    assert format_quant_num(18.2, kind="bps", explicit_sign=True) == "+18.2 bps"


def test_opencode_terminal_integration():
    backend = ExistingSystemBackend()
    term = OpenCodeTerminal(backend)
    
    # Automation command
    auto_resp, _ = term.handle("/automation")
    assert "AUTOMATIONS" in auto_resp
    assert "[Create] [Pause] [Resume] [History]" in auto_resp

    # Finance agent command
    agent_resp, _ = term.handle("/finance-agent NVDA")
    assert "Analyzing NVDA..." in agent_resp
    assert "[Open analysis ↗] [Run research] [Simulate]" in agent_resp

    # Kill switch command
    halt_resp, _ = term.handle("/kill CONFIRM")
    assert "EXECUTION HALTED" in halt_resp

    # Browser open command
    open_resp, _ = term.handle("/open NVDA")
    assert "Browser workspace →" in open_resp
    assert "NVDA" in open_resp
    assert "delta://" in open_resp
    assert "Full visualization opened in DELTA Web" in open_resp
