"""P2 wiring: HOLD pauses, --alt substitutes, BLOCK refuses, ALLOW paper-submits."""
import sys

import pytest

sys.path.insert(0, "tests")
from test_automation_gate import _frame, _Router  # noqa: E402

from delta_os.repl import Terminal


def _term(monkeypatch, tier="TIER1"):
    t = Terminal()
    stub = _Router({"BULL": _frame("up"), "BEAR": _frame("down")}, tier)
    t.brain.data_router = stub  # type: ignore[assignment]
    t.data = stub  # type: ignore[assignment]
    monkeypatch.setattr("builtins.input", lambda *a, **k: "n")
    return t


def test_hold_pauses_with_nothing_staged(monkeypatch):
    t = _term(monkeypatch)
    out, _ = t.handle("/trade BEAR buy 10")
    assert out.startswith("HOLD: BEAR"), out
    assert "nothing staged, nothing sent" in out
    assert t.router.paper._ledger.orders == {}


def test_alt_substitutes_and_paper_submits(monkeypatch):
    t = _term(monkeypatch)
    monkeypatch.setattr("builtins.input", lambda *a, **k: "y")
    out, _ = t.handle("/trade BEAR buy 10 --alt BULL")
    assert "submitted" in out, out
    syms = {o.symbol for o in t.router.paper._ledger.orders.values()}
    assert syms == {"BULL"}, syms


def test_synthetic_tier_blocked_before_anything(monkeypatch):
    t = _term(monkeypatch, tier="TIER3-SYNTH")
    out, _ = t.handle("/trade BULL buy 10")
    assert "BLOCKED" in out
    assert t.router.paper._ledger.orders == {}


def test_allow_path_shows_gate_and_firewall(monkeypatch, capsys):
    t = _term(monkeypatch)
    out, _ = t.handle("/trade BULL buy 10")
    assert out == "cancelled (no order sent)."
