"""Structured JSON-lines logging with secret redaction and trace correlation."""
from __future__ import annotations

import json
from datetime import datetime, timezone


class JsonLogger:
    def __init__(self, component: str, sink: list | None = None) -> None:
        from security.redaction import redact_secrets

        if not component.strip():
            raise ValueError("component required.")
        self._component = component
        self._sink = sink if sink is not None else []
        self._redact = redact_secrets

    def log(self, level: str, msg: str, *, trace_id: str = "", extra: dict | None = None) -> dict:
        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": level,
            "component": self._component,
            "trace_id": trace_id,
            "msg": self._redact(msg),
        }
        if extra:
            record["extra"] = json.loads(json.dumps(extra, default=str))
        self._sink.append(record)
        return record

    @property
    def records(self) -> tuple[dict, ...]:
        return tuple(self._sink)
