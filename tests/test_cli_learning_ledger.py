"""Durable CLI learning ledger contract and tamper detection."""

from __future__ import annotations

import sqlite3

from learning.cli_outcome_store import append_outcome, verify_ledger


def _event(decision_id="d-1", actual="-0.02"):
    return {
        "decision_id": decision_id,
        "instrument": "AAPL",
        "horizon": "5d",
        "regime": "mixed",
        "expected_return": "0.01",
        "actual_return": actual,
        "failure_type": "MODEL_ERROR",
        "lesson": "Re-check the OOS signal.",
        "experience_id": "exp-" + decision_id,
        "model_version": "strategy-v1",
        "evidence_status": "MANUAL_UNVERIFIED",
        "promotion_eligible": False,
        "source": "cli-manual-entry",
    }


def test_learning_ledger_persists_and_hash_links(tmp_path):
    path = tmp_path / "learning" / "outcomes.sqlite3"

    first = append_outcome(_event("d-1"), path)
    second = append_outcome(_event("d-2", "0.005"), path)

    assert first.sequence == 1
    assert second.sequence == 2
    assert second.previous_hash == first.event_hash
    result = verify_ledger(path)
    assert result["valid"] is True
    assert result["count"] == 2
    assert result["last_hash"] == second.event_hash


def test_learning_ledger_rejects_promotion_eligible_manual_notes(tmp_path):
    event = _event()
    event["promotion_eligible"] = True
    try:
        append_outcome(event, tmp_path / "outcomes.sqlite3")
    except ValueError as exc:
        assert "never promotion-eligible" in str(exc)
    else:
        raise AssertionError("manual CLI outcome must not be promotion evidence")


def test_learning_ledger_detects_tampered_record(tmp_path):
    path = tmp_path / "outcomes.sqlite3"
    append_outcome(_event(), path)

    conn = sqlite3.connect(path)
    conn.execute(
        "UPDATE cli_learning_outcomes SET event_json=? WHERE sequence=1",
        ('{"actual_return":"0.99"}',),
    )
    conn.commit()
    conn.close()

    result = verify_ledger(path)
    assert result["valid"] is False
    assert result["first_bad_sequence"] == 1
