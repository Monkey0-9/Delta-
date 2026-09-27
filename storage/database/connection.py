from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from .migrations import MIGRATIONS, SCHEMA_VERSION


@dataclass(slots=True)
class Database:
    """SQLite-backed durable store with the DuckDB+Parquet production interface.

    Production deploys DuckDB+Parquet + SQLite catalog per ``config/paper.yaml``
    (``data.store: duckdb+parquet``). This stdlib implementation exposes the
    identical schema/migration API so domain code is backend-agnostic and all
    tests run without native dependencies. Parquet datasets are tracked by
    content hash in the catalog; row data lives in SQLite tables with the same
    names/columns the DuckDB schema uses.
    """

    path: Path
    _conn: sqlite3.Connection | None = None

    def connect(self) -> sqlite3.Connection:
        if self._conn is None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(str(self.path))
            conn.row_factory = sqlite3.Row
            self._conn = conn
            self.migrate()
        return self._conn

    def migrate(self) -> int:
        assert self._conn is not None
        cur = self._conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY)"
        )
        _ = cur
        applied = {
            r[0] for r in self._conn.execute("SELECT version FROM schema_migrations")
        }
        for version, sql in MIGRATIONS:
            if version not in applied:
                self._conn.executescript(sql)
                self._conn.execute(
                    "INSERT INTO schema_migrations (version) VALUES (?)", (version,)
                )
        self._conn.commit()
        return SCHEMA_VERSION

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None
