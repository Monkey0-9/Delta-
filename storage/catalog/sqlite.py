from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Artifact:
    artifact_id: str
    artifact_type: str
    version: str
    path: str
    content_hash: str
    metadata: dict[str, Any]


class SQLiteCatalog:

    def __init__(self, database: Path):
        self.database = database

        database.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        with sqlite3.connect(database) as con:
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS artifacts (
                    artifact_id TEXT PRIMARY KEY,
                    artifact_type TEXT NOT NULL,
                    version TEXT NOT NULL,
                    path TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    created_at TEXT
                        NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

    @staticmethod
    def digest(value: Any) -> str:
        payload = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")

        return hashlib.sha256(
            payload
        ).hexdigest()

    def put(self, artifact: Artifact) -> None:

        with sqlite3.connect(
            self.database
        ) as con:
            con.execute(
                """
                INSERT OR REPLACE INTO artifacts
                (
                    artifact_id,
                    artifact_type,
                    version,
                    path,
                    content_hash,
                    metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    artifact.artifact_id,
                    artifact.artifact_type,
                    artifact.version,
                    artifact.path,
                    artifact.content_hash,
                    json.dumps(
                        artifact.metadata,
                        sort_keys=True,
                    ),
                ),
            )

    def get(
        self,
        artifact_id: str,
    ) -> Artifact | None:

        with sqlite3.connect(
            self.database
        ) as con:
            row = con.execute(
                """
                SELECT
                    artifact_id,
                    artifact_type,
                    version,
                    path,
                    content_hash,
                    metadata_json
                FROM artifacts
                WHERE artifact_id = ?
                """,
                (artifact_id,),
            ).fetchone()

        if row is None:
            return None

        return Artifact(
            artifact_id=row[0],
            artifact_type=row[1],
            version=row[2],
            path=row[3],
            content_hash=row[4],
            metadata=json.loads(row[5]),
        )