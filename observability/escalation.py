"""O-item (P4): persistent alert escalation with acknowledgement.

Detection (ops_rules + sre_check) is not paging. This module is the missing
half: every firing rule enters an tracked event; unacknowledged criticals
escalate on a schedule; acknowledgement stops escalation. State is a JSON
file (atomic write + fsync) so restarts neither lose nor duplicate pages.
Delivery itself stays in delta_os/alerting.py (Telegram/WhatsApp when
vault-configured); this module decides WHEN to page and records WHAT happened.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

ESCALATION_VERSION = "escalation-v1"

# severity -> minutes before each escalation level fires
ESCALATION_SCHEDULE: dict[str, tuple[int, ...]] = {
    "critical": (0, 5, 15),
    "warning": (15,),
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class EscalationEvent:
    event_id: str
    rule: str
    severity: str
    message: str
    first_fired_utc: str
    last_update_utc: str
    level: int = 0  # highest escalation level fired so far
    acked_by: str | None = None
    acked_utc: str | None = None
    pages_sent: int = 0


class EscalationTracker:
    """Persistent escalation state. Clock-injectable for tests."""

    def __init__(self, path: str | Path, now=None) -> None:
        self.path = Path(path)
        self._now = now or _utcnow
        self._events: dict[str, EscalationEvent] = {}
        if self.path.exists():
            self._load()

    # -- persistence ------------------------------------------------------
    def _snapshot(self) -> dict:
        return {"version": ESCALATION_VERSION,
                "events": {eid: vars(e) for eid, e in self._events.items()}}

    def _persist(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_name(f"{self.path.name}.{os.getpid()}.tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self._snapshot(), f, sort_keys=True)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, self.path)

    def _load(self) -> None:
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict) or raw.get("version") != ESCALATION_VERSION:
            raise ValueError(f"unrecognized escalation state in {self.path}")
        for eid, d in raw.get("events", {}).items():
            self._events[eid] = EscalationEvent(
                event_id=eid, rule=d["rule"], severity=d["severity"],
                message=d["message"], first_fired_utc=d["first_fired_utc"],
                last_update_utc=d["last_update_utc"],
                level=int(d.get("level", 0)), acked_by=d.get("acked_by"),
                acked_utc=d.get("acked_utc"),
                pages_sent=int(d.get("pages_sent", 0)))

    # -- operations --------------------------------------------------------
    def report(self, rule: str, severity: str, message: str) -> EscalationEvent:
        """Record a firing rule. Same rule+severity re-fires update the
        existing open event (no duplicate pages); resolved rules must call
        resolve() explicitly."""
        now = self._now().isoformat()
        for e in self._events.values():
            if (e.rule == rule and e.severity == severity
                    and e.acked_by is None):
                e.message = message
                e.last_update_utc = now
                self._persist()
                return e
        eid = f"{rule}:{severity}:{len(self._events) + 1}"
        e = EscalationEvent(event_id=eid, rule=rule, severity=severity,
                            message=message, first_fired_utc=now,
                            last_update_utc=now)
        self._events[eid] = e
        self._persist()
        return e

    def acknowledge(self, event_id: str, actor: str) -> EscalationEvent:
        e = self._events[event_id]  # KeyError on unknown id: loud, not silent
        if not actor.strip():
            raise ValueError("ack requires an actor identity.")
        e.acked_by = actor.strip()
        e.acked_utc = self._now().isoformat()
        self._persist()
        return e

    def resolve(self, event_id: str) -> None:
        del self._events[event_id]  # KeyError on unknown id
        self._persist()

    def due_pages(self) -> list[EscalationEvent]:
        """Open events whose next escalation level is due. Firing a level
        mutates level/pages_sent and persists (exactly-once per level)."""
        now = self._now()
        due = []
        for e in self._events.values():
            if e.acked_by is not None:
                continue
            schedule = ESCALATION_SCHEDULE.get(e.severity, ())
            if e.level >= len(schedule):
                continue
            first = datetime.fromisoformat(e.first_fired_utc)
            if first.tzinfo is None:
                first = first.replace(tzinfo=timezone.utc)
            elapsed_min = (now - first).total_seconds() / 60.0
            if elapsed_min >= schedule[e.level]:
                e.level += 1
                e.pages_sent += 1
                e.last_update_utc = now.isoformat()
                due.append(e)
        if due:
            self._persist()
        return due

    def open_events(self) -> list[EscalationEvent]:
        return [e for e in self._events.values() if e.acked_by is None]


__all__ = ["EscalationTracker", "EscalationEvent", "ESCALATION_VERSION",
           "ESCALATION_SCHEDULE"]
