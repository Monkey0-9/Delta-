"""P1/§9: retired and reference-only modules stay out of production paths."""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

# module -> reason it must not appear in production imports
RETIRED = {
    "execution.oms.state_machine": "retired legacy (ADR-0008); canonical is core.oms",
    "agents.fleet": "reference fixtures/test oracles only; not a decision path",
}

PRODUCTION_PATHS = [
    "core/oms/gateway.py",
    "core/oms/journal.py",
    "delta_os/repl.py",
    "delta_os/bridge.py",
    "execution/live_engine.py",
    "risk/firewall/firewall.py",
]


def test_no_retired_imports_in_production():
    violations = []
    for rel in PRODUCTION_PATHS:
        text = (REPO / rel).read_text(encoding="utf-8")
        for mod, reason in RETIRED.items():
            if re.search(rf"^\s*(from|import)\s+{re.escape(mod)}",
                         text, re.MULTILINE):
                violations.append(f"{rel} imports {mod} ({reason})")
    assert not violations, violations


def test_fleet_labeled_reference_only():
    text = (REPO / "agents" / "fleet.py").read_text(encoding="utf-8")
    head = "\n".join(text.splitlines()[:15]).lower()
    assert "reference" in head or "fixture" in head or "oracle" in head, (
        "agents/fleet.py must label itself reference-only at the top")


def test_planner_labels_heuristic_mode():
    from agent.planner.planner import AgentPlan

    assert AgentPlan(task_id=__import__("uuid").uuid4(),
                     steps=()).planning_mode == "heuristic-keyword"
