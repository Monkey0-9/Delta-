"""DELTA OS — Storage, SQLite WAL & Ledger Crash Recovery Engine.

Institutional self-healing and recovery procedures for mission-critical state:
1. SQLite WAL integrity inspection (PRAGMA integrity_check, quick_check, wal_checkpoint).
2. Atomic quarantine of corrupted databases with forensic preservation.
3. Recovery and healing of torn JSONL ledgers (recovering from kill -9 during appends).
4. Automated critical paging upon corruption detection.
"""
from __future__ import annotations

import datetime
import json
import logging
import os
from pathlib import Path
import shutil
import sqlite3
from typing import Any, Dict, List, Optional, Tuple

from delta_os.paging import PagingDispatcher

logger = logging.getLogger("delta_os.storage_recovery")


class StorageIntegrityError(RuntimeError):
    """Raised when critical storage fails integrity checks and cannot be safely loaded."""


class StorageRecoveryEngine:
    """Manages crash recovery, WAL checkpointing, and torn-write healing."""

    def __init__(self, pager: Optional[PagingDispatcher] = None) -> None:
        self.pager = pager or PagingDispatcher()

    def configure_resilient_sqlite(self, conn: sqlite3.Connection) -> None:
        """Apply institutional resiliency pragmas to an open SQLite connection."""
        cursor = conn.cursor()
        cursor.execute("PRAGMA journal_mode = WAL;")
        cursor.execute("PRAGMA synchronous = NORMAL;")
        cursor.execute("PRAGMA busy_timeout = 5000;")
        cursor.close()

    def verify_and_checkpoint_sqlite(
        self,
        db_path: Path | str,
        quarantine_if_corrupt: bool = True,
    ) -> Tuple[bool, str]:
        """Verify SQLite database integrity and execute a WAL checkpoint.
        
        Returns:
            (healthy: bool, detail_message: str)
        """
        p = Path(db_path)
        if not p.exists():
            return True, f"Database {p} does not exist yet (clean state)."

        conn: Optional[sqlite3.Connection] = None
        try:
            conn = sqlite3.connect(str(p), timeout=5.0)
            cursor = conn.cursor()

            # 1. Quick check
            cursor.execute("PRAGMA quick_check;")
            row = cursor.fetchone()
            if not row or row[0] != "ok":
                raise StorageIntegrityError(f"quick_check failed: {row}")

            # 2. Comprehensive integrity check
            cursor.execute("PRAGMA integrity_check;")
            row = cursor.fetchone()
            if not row or row[0] != "ok":
                raise StorageIntegrityError(f"integrity_check failed: {row}")

            # 3. Truncate WAL to flush journal to main database file
            cursor.execute("PRAGMA wal_checkpoint(TRUNCATE);")
            cursor.close()
            conn.close()
            conn = None

            return True, f"SQLite database {p.name} verified healthy; WAL checkpointed."

        except Exception as exc:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

            msg = f"Database integrity check failed for {p}: {exc}"
            logger.critical(msg)

            # Fire critical alert
            self.pager.dispatch(
                severity="CRITICAL",
                component="storage_recovery",
                message=f"[SQLITE_INTEGRITY_FAIL] {msg}",
                metadata={"rule": "SQLITE_INTEGRITY_FAIL"},
            )

            if quarantine_if_corrupt:
                now_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
                corrupt_path = p.with_name(f"{p.name}.corrupt-{now_str}")
                try:
                    shutil.move(str(p), str(corrupt_path))
                    # Also move WAL and SHM if present
                    for ext in ["-wal", "-shm"]:
                        aux = Path(f"{p}{ext}")
                        if aux.exists():
                            shutil.move(str(aux), str(f"{corrupt_path}{ext}"))
                    logger.warning(f"Quarantined corrupt database to {corrupt_path}")
                    return False, f"QUARANTINED: Damaged DB moved to {corrupt_path.name}"
                except Exception as move_err:
                    return False, f"CRITICAL: Failed to quarantine damaged DB: {move_err}"

            return False, msg

    def recover_torn_jsonl_ledger(
        self,
        jsonl_path: Path | str,
    ) -> Tuple[int, int, str]:
        """Scan a JSONL ledger, drop torn trailing lines resulting from kill -9, and save clean state.
        
        Returns:
            (valid_records_count, dropped_lines_count, status_message)
        """
        p = Path(jsonl_path)
        if not p.exists():
            return 0, 0, f"File {p} does not exist."

        valid_lines: List[str] = []
        dropped_lines = 0

        with open(p, "rb") as f:
            raw_bytes = f.read()

        text = raw_bytes.decode("utf-8", errors="replace")
        lines = text.splitlines()

        for idx, line in enumerate(lines, start=1):
            line_str = line.strip()
            if not line_str:
                continue
            try:
                data = json.loads(line_str)
                if isinstance(data, dict):
                    valid_lines.append(line_str)
                else:
                    dropped_lines += 1
            except Exception:
                # Torn line found (e.g. power cutoff mid-write)
                dropped_lines += 1
                logger.warning(f"Dropping torn record at line {idx} in {p}")

        if dropped_lines > 0:
            # Backup original and write cleaned ledger atomically
            now_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            backup_path = p.with_name(f"{p.name}.torn-{now_str}")
            shutil.copyfile(str(p), str(backup_path))

            tmp_path = p.with_name(f"{p.name}.clean.tmp")
            with open(tmp_path, "w", encoding="utf-8") as f:
                for v in valid_lines:
                    f.write(f"{v}\n")
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, p)

            self.pager.dispatch(
                severity="WARNING",
                component="storage_recovery",
                message=f"[TORN_JSONL_RECOVERED] Recovered {len(valid_lines)} valid records from {p.name}; dropped {dropped_lines} torn lines.",
                metadata={"rule": "TORN_JSONL_RECOVERED"},
            )
            msg = f"REPAIRED: Dropped {dropped_lines} torn line(s). Backup preserved at {backup_path.name}."
        else:
            msg = f"CLEAN: All {len(valid_lines)} records verified."

        return len(valid_lines), dropped_lines, msg


__all__ = [
    "StorageIntegrityError",
    "StorageRecoveryEngine",
]
