"""FIX persistent sequence and message journal store.

Provides durable tracking of inbound/outbound FIX MsgSeqNum and raw FIX message logs
to guarantee zero sequence loss across process restarts or abrupt network disconnects.
"""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Optional, Tuple, List, Dict


class FixSequenceStore:
    """Durable SQLite-backed FIX sequence and message store."""

    def __init__(self, db_path: str | Path = ":memory:"):
        self.db_path = str(db_path)
        if self.db_path != ":memory:":
            os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._init_db()

    def _init_db(self) -> None:
        with self._conn:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS fix_sessions (
                    session_id TEXT PRIMARY KEY,
                    sender_comp_id TEXT NOT NULL,
                    target_comp_id TEXT NOT NULL,
                    out_seq INTEGER NOT NULL DEFAULT 1,
                    in_seq INTEGER NOT NULL DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS fix_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    direction TEXT NOT NULL, -- 'OUT' or 'IN'
                    seq_num INTEGER NOT NULL,
                    msg_type TEXT NOT NULL,
                    raw_message TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(session_id) REFERENCES fix_sessions(session_id)
                )
                """
            )

    def get_session_seq(self, session_id: str) -> Tuple[int, int]:
        """Returns (out_seq, in_seq) for the given session_id."""
        with self._conn:
            cursor = self._conn.cursor()
            cursor.execute(
                "SELECT out_seq, in_seq FROM fix_sessions WHERE session_id = ?",
                (session_id,),
            )
            row = cursor.fetchone()
            if row:
                return int(row[0]), int(row[1])
            return 1, 1

    def init_session(self, session_id: str, sender_comp_id: str, target_comp_id: str) -> Tuple[int, int]:
        """Initialize or load session sequence state."""
        with self._conn:
            cursor = self._conn.cursor()
            cursor.execute(
                "SELECT out_seq, in_seq FROM fix_sessions WHERE session_id = ?",
                (session_id,),
            )
            row = cursor.fetchone()
            if row:
                return int(row[0]), int(row[1])
            cursor.execute(
                """
                INSERT INTO fix_sessions (session_id, sender_comp_id, target_comp_id, out_seq, in_seq)
                VALUES (?, ?, ?, 1, 1)
                """,
                (session_id, sender_comp_id, target_comp_id),
            )
            return 1, 1

    def update_seq(self, session_id: str, out_seq: Optional[int] = None, in_seq: Optional[int] = None) -> None:
        """Update outbound or inbound sequence number."""
        with self._conn:
            if out_seq is not None and in_seq is not None:
                self._conn.execute(
                    "UPDATE fix_sessions SET out_seq = ?, in_seq = ?, updated_at = CURRENT_TIMESTAMP WHERE session_id = ?",
                    (out_seq, in_seq, session_id),
                )
            elif out_seq is not None:
                self._conn.execute(
                    "UPDATE fix_sessions SET out_seq = ?, updated_at = CURRENT_TIMESTAMP WHERE session_id = ?",
                    (out_seq, session_id),
                )
            elif in_seq is not None:
                self._conn.execute(
                    "UPDATE fix_sessions SET in_seq = ?, updated_at = CURRENT_TIMESTAMP WHERE session_id = ?",
                    (in_seq, session_id),
                )

    def log_message(self, session_id: str, direction: str, seq_num: int, msg_type: str, raw_message: str) -> None:
        """Log raw FIX message to durable storage."""
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO fix_messages (session_id, direction, seq_num, msg_type, raw_message)
                VALUES (?, ?, ?, ?, ?)
                """,
                (session_id, direction, seq_num, msg_type, raw_message),
            )

    def get_messages(self, session_id: str, direction: str, start_seq: int, end_seq: int) -> List[Tuple[int, str, str]]:
        """Fetch range of logged messages for ResendRequest gap fills."""
        with self._conn:
            cursor = self._conn.cursor()
            cursor.execute(
                """
                SELECT seq_num, msg_type, raw_message FROM fix_messages
                WHERE session_id = ? AND direction = ? AND seq_num >= ? AND seq_num <= ?
                ORDER BY seq_num ASC
                """,
                (session_id, direction, start_seq, end_seq),
            )
            return [(int(r[0]), str(r[1]), str(r[2])) for r in cursor.fetchall()]

    def close(self) -> None:
        self._conn.close()


__all__ = ["FixSequenceStore"]
