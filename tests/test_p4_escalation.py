"""O-item: escalation fires on schedule, acks stop it, restarts keep it."""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone

import pytest

sys.path.insert(0, ".")

from observability.escalation import EscalationTracker


def _clock(start: datetime):
    now = {"t": start}
    return now, lambda: now["t"]


def test_critical_pages_immediately_then_escalates(tmp_path):
    now, clock = _clock(datetime(2026, 10, 11, 12, 0, tzinfo=timezone.utc))
    tr = EscalationTracker(tmp_path / "esc.json", now=clock)
    e = tr.report("kill-switch-engaged", "critical", "halted")
    due = tr.due_pages()  # level 0 at minute 0
    assert [d.event_id for d in due] == [e.event_id]
    assert e.pages_sent == 1
    assert tr.due_pages() == []  # exactly once per level
    now["t"] += timedelta(minutes=6)
    due = tr.due_pages()  # level 1 at minute 5
    assert [d.event_id for d in due] == [e.event_id]
    assert e.pages_sent == 2


def test_ack_stops_escalation_and_rejects_anonymous(tmp_path):
    now, clock = _clock(datetime(2026, 10, 11, 12, 0, tzinfo=timezone.utc))
    tr = EscalationTracker(tmp_path / "esc.json", now=clock)
    e = tr.report("risk-latency-p99-hot", "warning", "slow")
    assert tr.due_pages() == []  # warnings page at minute 15, not 0
    with pytest.raises(ValueError):
        tr.acknowledge(e.event_id, "  ")
    tr.acknowledge(e.event_id, actor="ops-oncall")
    now["t"] += timedelta(minutes=30)
    assert tr.due_pages() == []
    assert tr.open_events() == []


def test_refire_updates_without_duplicating(tmp_path):
    now, clock = _clock(datetime(2026, 10, 11, 12, 0, tzinfo=timezone.utc))
    tr = EscalationTracker(tmp_path / "esc.json", now=clock)
    e1 = tr.report("sequence-gaps", "warning", "gaps=1")
    e2 = tr.report("sequence-gaps", "warning", "gaps=4")
    assert e1.event_id == e2.event_id
    assert len(tr.open_events()) == 1


def test_restart_preserves_open_escalations(tmp_path):
    now, clock = _clock(datetime(2026, 10, 11, 12, 0, tzinfo=timezone.utc))
    tr = EscalationTracker(tmp_path / "esc.json", now=clock)
    e = tr.report("kill-switch-engaged", "critical", "halted")
    tr.due_pages()
    tr2 = EscalationTracker(tmp_path / "esc.json", now=clock)
    reopened = tr2.open_events()
    assert len(reopened) == 1 and reopened[0].pages_sent == 1
    assert reopened[0].event_id == e.event_id
    # Refusing to acknowledge an unknown id is loud.
    with pytest.raises(KeyError):
        tr2.acknowledge("nope", actor="ops")
