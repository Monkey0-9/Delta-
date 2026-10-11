"""P1: compliance ledger survives restarts and refuses tampered loads."""
from __future__ import annotations

import json
import sys

import pytest

sys.path.insert(0, ".")

from governance.compliance import ComplianceLog, ComplianceTamperError


def test_restart_preserves_and_verifies_chain(tmp_path):
    p = tmp_path / "compliance.jsonl"
    log = ComplianceLog(p)
    log.append("order", {"order_id": "A1"})
    log.append("kill", {"actor": "ops"})
    assert log.verify() is True

    reopened = ComplianceLog(p)
    assert len(reopened) == 2
    assert reopened.verify() is True
    assert [r.kind for r in reopened._records] == ["order", "kill"]
    # Chain continues across the restart (prev links to reloaded head).
    reopened.append("reset", {"actor": "ops"})
    assert reopened.verify() is True
    assert len(ComplianceLog(p)) == 3


def test_tampered_file_refused_and_preserved(tmp_path):
    p = tmp_path / "compliance.jsonl"
    log = ComplianceLog(p)
    log.append("order", {"order_id": "A1"})

    lines = p.read_text(encoding="utf-8").splitlines()
    rec = json.loads(lines[0])
    rec["payload"] = {"order_id": "EVIL"}
    p.write_text(json.dumps(rec) + "\n", encoding="utf-8")

    with pytest.raises(ComplianceTamperError):
        ComplianceLog(p)
    backups = list(tmp_path.glob("compliance.jsonl.corrupt-*"))
    assert len(backups) == 1, "corrupt ledger must be preserved as evidence"


def test_torn_tail_refused(tmp_path):
    p = tmp_path / "compliance.jsonl"
    log = ComplianceLog(p)
    log.append("order", {"order_id": "A1"})
    with open(p, "ab") as f:
        f.write(b'{"seq": 1, "kind": "ord')
    with pytest.raises(ComplianceTamperError):
        ComplianceLog(p)


def test_safety_state_uses_durable_ledger(monkeypatch, tmp_path):
    from delta_os import safety as safety_mod
    from delta_os.safety import SafetyState

    monkeypatch.setattr(safety_mod, "_session_path",
                        lambda: tmp_path / "session.json")
    s = SafetyState()
    s.compliance.append("kill", {"actor": "test"})
    # A new state (simulated restart) reloads the same ledger.
    s2 = SafetyState()
    assert len(s2.compliance) == 1
    assert s2.compliance.verify() is True
