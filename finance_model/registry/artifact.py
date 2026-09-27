from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class ModelArtifact:
    model_id: str
    version: str

    base_model: str

    dataset_hash: str
    code_version: str

    created_at: datetime

    task: str

    training_config_hash: str

    evaluation_hash: str

    status: str = "EXPERIMENTAL"

    @property
    def artifact_hash(self) -> str:
        payload = asdict(self)
        payload["created_at"] = self.created_at.isoformat()

        raw = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()

        return hashlib.sha256(raw).hexdigest()