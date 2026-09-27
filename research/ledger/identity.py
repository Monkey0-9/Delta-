from __future__ import annotations

import hashlib
import json
from typing import Any


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def experiment_hash(
    *,
    hypothesis: str,
    dataset_hash: str,
    model_version: str,
    parameters: dict[str, Any],
    seed: int,
) -> str:
    payload = {
        "hypothesis": hypothesis,
        "dataset_hash": dataset_hash,
        "model_version": model_version,
        "parameters": parameters,
        "seed": seed,
    }

    return hashlib.sha256(
        canonical_json(payload).encode("utf-8")
    ).hexdigest()