from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class RepositoryIndex:
    """Catalog for DuckDB+Parquet datasets (SQLite-backed in production)."""

    _datasets: dict[str, str] = field(default_factory=dict)  # name -> parquet path/hash

    def register(self, name: str, content_hash: str) -> None:
        self._datasets[name] = content_hash

    def get(self, name: str) -> str:
        return self._datasets[name]

    def list(self) -> tuple[str, ...]:
        return tuple(sorted(self._datasets))

    def remove(self, name: str) -> None:
        if name not in self._datasets:
            raise KeyError(f"unknown dataset: {name}")
        del self._datasets[name]


@dataclass(slots=True)
class PersistentCatalog:
    """SQLite-backed catalog with versioned dataset rows + migrations.

    Same table layout as the DuckDB production schema
    (``storage/database/migrations.py`` v1 ``catalog_datasets``).
    """

    db_path: str | Path

    def _connect(self) -> sqlite3.Connection:
        from storage.database.connection import Database

        return Database(Path(self.db_path)).connect()

    def register(
        self, name: str, content_hash: str, parquet_path: str = "", version: int = 1
    ) -> None:
        if not name or not content_hash:
            raise ValueError("name/content_hash cannot be empty.")
        conn = self._connect()
        conn.execute(
            "INSERT INTO catalog_datasets (name, content_hash, parquet_path, version)"
            " VALUES (?, ?, ?, ?)"
            " ON CONFLICT(name) DO UPDATE SET content_hash=excluded.content_hash,"
            " parquet_path=excluded.parquet_path, version=excluded.version",
            (name, content_hash, parquet_path or f"datasets/{name}.parquet", version),
        )
        conn.commit()

    def get(self, name: str) -> str:
        conn = self._connect()
        row = conn.execute(
            "SELECT content_hash FROM catalog_datasets WHERE name = ?", (name,)
        ).fetchone()
        if row is None:
            raise KeyError(f"unknown dataset: {name}")
        return str(row[0])

    def describe(self, name: str) -> dict[str, object]:
        conn = self._connect()
        row = conn.execute(
            "SELECT name, content_hash, parquet_path, version FROM catalog_datasets"
            " WHERE name = ?",
            (name,),
        ).fetchone()
        if row is None:
            raise KeyError(f"unknown dataset: {name}")
        return {
            "name": row[0],
            "content_hash": row[1],
            "parquet_path": row[2],
            "version": row[3],
        }

    def list(self) -> tuple[str, ...]:
        conn = self._connect()
        return tuple(
            r[0]
            for r in conn.execute("SELECT name FROM catalog_datasets ORDER BY name")
        )
