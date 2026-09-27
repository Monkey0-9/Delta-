from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True, slots=True)
class DatasetManifest:
    dataset_id: str
    version: str

    created_at: datetime

    source_hashes: tuple[str, ...]
    record_count: int

    train_count: int
    validation_count: int
    test_count: int

    schema_version: str

    metadata: dict[str, str] = field(default_factory=dict)

    @property
    def dataset_hash(self) -> str:
        payload = {
            "dataset_id": self.dataset_id,
            "version": self.version,
            "source_hashes": self.source_hashes,
            "record_count": self.record_count,
            "train_count": self.train_count,
            "validation_count": self.validation_count,
            "test_count": self.test_count,
            "schema_version": self.schema_version,
        }

        raw = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()

        return hashlib.sha256(raw).hexdigest()

    def save(self, path: str | Path) -> None:
        Path(path).write_text(
            json.dumps(
                {
                    "dataset_id": self.dataset_id,
                    "version": self.version,
                    "created_at": self.created_at.isoformat(),
                    "source_hashes": self.source_hashes,
                    "record_count": self.record_count,
                    "train_count": self.train_count,
                    "validation_count": self.validation_count,
                    "test_count": self.test_count,
                    "schema_version": self.schema_version,
                    "dataset_hash": self.dataset_hash,
                    "metadata": self.metadata,
                },
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )