from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Any


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def canonical_hash(value: Any) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")

    return sha256(payload).hexdigest()


@dataclass(frozen=True)
class ExperimentSpec:
    experiment_id: str
    hypothesis: str

    code_commit: str
    dataset_id: str
    dataset_hash: str

    model_id: str | None

    random_seed: int

    universe: str
    train_start: str
    train_end: str
    validation_start: str
    validation_end: str
    test_start: str
    test_end: str

    cost_model: str
    parameters: dict[str, Any] = field(default_factory=dict)

    created_at: datetime = field(default_factory=utc_now)

    def fingerprint(self) -> str:
        return canonical_hash(
            {
                "experiment_id": self.experiment_id,
                "hypothesis": self.hypothesis,
                "code_commit": self.code_commit,
                "dataset_id": self.dataset_id,
                "dataset_hash": self.dataset_hash,
                "model_id": self.model_id,
                "random_seed": self.random_seed,
                "universe": self.universe,
                "train_start": self.train_start,
                "train_end": self.train_end,
                "validation_start": self.validation_start,
                "validation_end": self.validation_end,
                "test_start": self.test_start,
                "test_end": self.test_end,
                "cost_model": self.cost_model,
                "parameters": self.parameters,
            }
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "hypothesis": self.hypothesis,
            "code_commit": self.code_commit,
            "dataset_id": self.dataset_id,
            "dataset_hash": self.dataset_hash,
            "model_id": self.model_id,
            "random_seed": self.random_seed,
            "universe": self.universe,
            "train_start": self.train_start,
            "train_end": self.train_end,
            "validation_start": self.validation_start,
            "validation_end": self.validation_end,
            "test_start": self.test_start,
            "test_end": self.test_end,
            "cost_model": self.cost_model,
            "parameters": self.parameters,
            "created_at": self.created_at.isoformat(),
            "fingerprint": self.fingerprint(),
        }