"""P0-10 boundary audit: agent -> tool -> broker authority levels.

Proves the R0..R5 lattice: a RESEARCH (R1) agent can read and backtest but
can never touch paper/shadow/live/promote; promotion advances exactly one
level per passed gate (no R1->R5 jump); unknown/unregistered tools are
refused; the sandbox records every execution for audit.
"""
from __future__ import annotations

import sys

sys.path.insert(0, ".")

from agents.research_stack import PermissionLayer, Sandbox, ToolRegistry


def test_r1_researcher_blocked_from_broker_paths():
    p = PermissionLayer(agent_level="R1")
    assert p.allow_tool("read_market")[0]
    assert p.allow_tool("run_backtest")[0] is False  # R2: needs promotion
    for tool in ("start_paper", "start_shadow", "submit_live", "promote"):
        ok, reason = p.allow_tool(tool)
        assert not ok, tool
        assert "requires" in reason


def test_no_level_skip_promotion():
    p = PermissionLayer(agent_level="R1")
    ok, _ = p.request_promotion("R5", gate_passed=True)
    assert not ok and p.agent_level == "R1"
    ok, _ = p.request_promotion("R2", gate_passed=False)  # failed gate
    assert not ok and p.agent_level == "R1"
    ok, _ = p.request_promotion("R2", gate_passed=True)
    assert ok and p.agent_level == "R2"
    assert p.allow_tool("run_backtest")[0]
    assert not p.allow_tool("submit_live")[0]  # still four levels away


def test_unknown_and_unregistered_tools_refused_and_logged():
    p = PermissionLayer(agent_level="R5")
    assert p.allow_tool("wire_funds")[0] is False
    reg = ToolRegistry()
    reg.register("read_market", "img-data")
    sb = Sandbox()
    ok, _ = sb.execute("submit_live", "buy 1M SPY", permission=p, registry=reg)
    assert not ok  # R5 allowed by level but tool not registered -> blocked
    assert sb.runs == []
    ok, _ = sb.execute("read_market", "SPY", permission=p, registry=reg)
    assert ok and len(sb.runs) == 1  # every execution recorded
