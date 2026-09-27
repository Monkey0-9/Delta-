from __future__ import annotations

from dataclasses import (
    dataclass,
    asdict,
)
from datetime import datetime, timezone
import hashlib
import json
import platform
import sys
from pathlib import Path
from typing import Any


def sha256_file(
    path: str | Path,
) -> str:

    digest = hashlib.sha256()

    with Path(path).open(
        "rb"
    ) as file:

        for chunk in iter(
            lambda:
                file.read(
                    1024 * 1024
                ),
            b"",
        ):

            digest.update(chunk)

    return digest.hexdigest()


@dataclass(frozen=True, slots=True)
class TrainingRun:

    run_id: str

    model_version: str

    dataset_hash: str

    config: dict[str, Any]

    seed: int

    python: str

    platform: str

    created_at: str

    status: str = "CREATED"

    @classmethod
    def create(
        cls,
        run_id,
        model_version,
        dataset_hash,
        config,
        seed,
    ):

        return cls(
            run_id=run_id,
            model_version=model_version,
            dataset_hash=dataset_hash,
            config=config,
            seed=seed,
            python=sys.version,
            platform=platform.platform(),
            created_at=datetime.now(
                timezone.utc
            ).isoformat(),
        )

    @property
    def run_hash(self) -> str:

        raw = json.dumps(
            asdict(self),
            sort_keys=True,
            separators=(",", ":"),
        ).encode()

        return hashlib.sha256(
            raw
        ).hexdigest()

    def save(
        self,
        path: str | Path,
    ) -> None:

        path = Path(path)

        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        payload = asdict(self)

        payload[
            "run_hash"
        ] = self.run_hash

        path.write_text(
            json.dumps(
                payload,
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )