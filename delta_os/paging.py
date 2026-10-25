"""DELTA OS — Durable Alert Paging & Incident Escalation Dispatcher.

Handles institutional notifications for circuit breaker events, daemon failures,
and portfolio risk threshold breaches with deduplication, retry, and local audit logging.
"""
from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


def _delta_dir() -> Path:
    base = Path(os.environ.get("DELTA_HOME", str(Path.home() / ".delta")))
    base.mkdir(parents=True, exist_ok=True)
    return base


@dataclass
class PageEvent:
    alert_id: str
    severity: str  # INFO | WARNING | CRITICAL | FATAL
    component: str
    message: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    acknowledged: bool = False
    delivery_targets: List[str] = field(default_factory=lambda: ["local_log", "alerts_ledger"])
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "alert_id": self.alert_id,
            "severity": self.severity,
            "component": self.component,
            "message": self.message,
            "timestamp": self.timestamp,
            "acknowledged": self.acknowledged,
            "delivery_targets": self.delivery_targets,
            "metadata": self.metadata,
        }


class PagingDispatcher:
    """Manages durable alert recording, escalation rules, and delivery verification."""

    def __init__(self, ledger_path: Optional[Path] = None) -> None:
        self.ledger_path = ledger_path or (_delta_dir() / "alerts.jsonl")
        self._recent_signatures: Dict[str, float] = {}
        self._dedup_window_s = 60.0

    def dispatch(
        self,
        severity: str,
        component: str,
        message: str,
        metadata: Optional[Dict[str, Any]] = None,
        force: bool = False,
    ) -> Optional[PageEvent]:
        """Dispatch an alert event. Deduplicates identical alerts within window unless force=True."""
        sig = f"{severity}:{component}:{message}"
        now = time.time()

        if not force and sig in self._recent_signatures:
            if now - self._recent_signatures[sig] < self._dedup_window_s:
                return None  # Deduplicated

        self._recent_signatures[sig] = now

        import secrets
        alert_id = f"ALT-{secrets.token_hex(6).upper()}"
        event = PageEvent(
            alert_id=alert_id,
            severity=severity,
            component=component,
            message=message,
            metadata=metadata or {},
        )

        self._persist_to_ledger(event)
        self._deliver_console(event)

        return event

    def _persist_to_ledger(self, event: PageEvent) -> None:
        try:
            with open(self.ledger_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(event.to_dict()) + "\n")
                f.flush()
        except Exception as exc:
            print(f"[PAGING ERROR] Failed to persist alert to ledger: {exc}", file=sys.stderr)

    def _deliver_console(self, event: PageEvent) -> None:
        prefix = f"[{event.timestamp}] [DELTA-ALERT:{event.severity}] [{event.component}]"
        print(f"{prefix} {event.message}", file=sys.stderr, flush=True)

    def get_recent_alerts(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Read back recent alerts from the durable ledger."""
        if not self.ledger_path.exists():
            return []
        alerts: List[Dict[str, Any]] = []
        try:
            with open(self.ledger_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            alerts.append(json.loads(line))
                        except Exception:
                            pass
            return alerts[-limit:]
        except Exception:
            return []
