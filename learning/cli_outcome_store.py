"""Durable, tamper-evident CLI outcome notes.

This store records operator-entered outcomes for retrospective review. Entries
are explicitly marked unverified and are never strategy/model-promotion evidence.
Broker-reconciled fills must be imported through a separate trusted adapter.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from uuid import uuid4

_ZERO_HASH = "0" * 64


@dataclass(frozen=True, slots=True)
class OutcomeReceipt:
    event_id: str
    sequence: int
    event_hash: str
    previous_hash: str
    path: str


def default_ledger_path() -> Path:
    configured = os.environ.get("DELTA_LEARNING_LEDGER", "").strip()
    if configured:
        return Path(configured).expanduser()
    return Path.home() / ".delta" / "learning" / "outcomes.sqlite3"


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _hash(previous_hash: str, event_json: str) -> str:
    envelope = {"previous_hash": previous_hash, "event": json.loads(event_json)}
    return hashlib.sha256(_canonical(envelope).encode("utf-8")).hexdigest()


def _connect(path: str | Path | None = None) -> tuple[sqlite3.Connection, str]:
    raw_path = str(path if path is not None else default_ledger_path())
    if raw_path != ":memory:":
        p = Path(raw_path).expanduser()
        p.parent.mkdir(parents=True, exist_ok=True)
        raw_path = str(p)
    conn = sqlite3.connect(raw_path, timeout=10.0, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=10000")
    conn.execute("PRAGMA synchronous=FULL")
    try:
        conn.execute("PRAGMA journal_mode=WAL")
    except sqlite3.DatabaseError:
        # In-memory test databases use a different journal mode; durability
        # for file-backed databases is still requested above.
        pass
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS cli_learning_outcomes (
            sequence INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id TEXT NOT NULL UNIQUE,
            timestamp_utc TEXT NOT NULL,
            previous_hash TEXT NOT NULL,
            event_json TEXT NOT NULL,
            event_hash TEXT NOT NULL
        )
        """
    )
    if raw_path != ":memory:":
        try:
            os.chmod(raw_path, 0o600)
        except OSError:
            pass
    return conn, raw_path


def append_outcome(
    event: Mapping[str, Any],
    path: str | Path | None = None,
) -> OutcomeReceipt:
    """Append a manual/unverified outcome under a SQLite transaction.

    The caller may not label an operator-entered record as promotion-eligible.
    Each event is immutable, hash-linked and flushed before success is returned.
    """
    required = (
        "decision_id", "instrument", "horizon", "regime",
        "expected_return", "actual_return", "failure_type", "lesson",
        "model_version", "evidence_status", "promotion_eligible",
    )
    missing = [name for name in required if name not in event]
    if missing:
        raise ValueError(f"outcome missing required fields: {', '.join(missing)}")
    if event.get("promotion_eligible") is not False:
        raise ValueError("CLI-entered outcomes are never promotion-eligible")
    if str(event.get("evidence_status", "")).upper() != "MANUAL_UNVERIFIED":
        raise ValueError("CLI outcome evidence_status must be MANUAL_UNVERIFIED")
    if not str(event.get("decision_id", "")).strip():
        raise ValueError("decision_id cannot be blank")
    if not str(event.get("instrument", "")).strip():
        raise ValueError("instrument cannot be blank")

    timestamp = datetime.now(timezone.utc).isoformat()
    event_id = uuid4().hex
    body = dict(event)
    body.update({
        "event_id": event_id,
        "timestamp_utc": timestamp,
        "schema_version": 1,
        "store_type": "manual-outcome-note",
    })
    event_json = _canonical(body)

    conn, actual_path = _connect(path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT sequence, event_hash FROM cli_learning_outcomes "
            "ORDER BY sequence DESC LIMIT 1"
        ).fetchone()
        previous_hash = str(row["event_hash"]) if row else _ZERO_HASH
        event_hash = _hash(previous_hash, event_json)
        cursor = conn.execute(
            """
            INSERT INTO cli_learning_outcomes
                (event_id, timestamp_utc, previous_hash, event_json, event_hash)
            VALUES (?, ?, ?, ?, ?)
            """,
            (event_id, timestamp, previous_hash, event_json, event_hash),
        )
        sequence = int(cursor.lastrowid)
        conn.commit()
        return OutcomeReceipt(
            event_id=event_id,
            sequence=sequence,
            event_hash=event_hash,
            previous_hash=previous_hash,
            path=actual_path,
        )
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def verify_ledger(path: str | Path | None = None) -> dict[str, Any]:
    """Verify sequence and hash linkage without changing any row."""
    conn, actual_path = _connect(path)
    try:
        rows = conn.execute(
            "SELECT sequence, previous_hash, event_json, event_hash "
            "FROM cli_learning_outcomes ORDER BY sequence"
        ).fetchall()
        expected_previous = _ZERO_HASH
        for row in rows:
            sequence = int(row["sequence"])
            stored_previous = str(row["previous_hash"])
            stored_json = str(row["event_json"])
            stored_hash = str(row["event_hash"])
            try:
                parsed = json.loads(stored_json)
                canonical = _canonical(parsed)
                computed_hash = _hash(expected_previous, canonical)
            except Exception:
                return {
                    "valid": False, "count": len(rows),
                    "first_bad_sequence": sequence, "path": actual_path,
                    "reason": "invalid_event_json",
                }
            if (stored_previous != expected_previous
                    or canonical != stored_json
                    or computed_hash != stored_hash):
                return {
                    "valid": False, "count": len(rows),
                    "first_bad_sequence": sequence, "path": actual_path,
                    "reason": "hash_or_link_mismatch",
                }
            expected_previous = stored_hash
        return {
            "valid": True,
            "count": len(rows),
            "last_hash": expected_previous,
            "path": actual_path,
        }
    finally:
        conn.close()


__all__ = ["OutcomeReceipt", "append_outcome", "default_ledger_path", "verify_ledger"]
