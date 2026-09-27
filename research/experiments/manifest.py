from __future__ import annotations

from dataclasses import (
    dataclass,
    asdict,
)
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any


def _hash(obj: Any) -> str:

    raw = json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode()

    return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True, slots=True)
class ExperimentManifest:

    experiment_id: str

    hypothesis: str

    strategy_version: str

    code_version: str

    dataset_hash: str

    universe: tuple[str, ...]

    start: str

    end: str

    seed: int

    config: dict[str, Any]

    created_at: str

    @classmethod
    def create(
        cls,
        *,
        experiment_id: str,
        hypothesis: str,
        strategy_version: str,
        code_version: str,
        dataset_hash: str,
        universe: tuple[str, ...],
        start: str,
        end: str,
        seed: int,
        config: dict[str, Any],
    ) -> "ExperimentManifest":

        return cls(
            experiment_id=experiment_id,
            hypothesis=hypothesis,
            strategy_version=strategy_version,
            code_version=code_version,
            dataset_hash=dataset_hash,
            universe=tuple(
                sorted(universe)
            ),
            start=start,
            end=end,
            seed=seed,
            config=config,
            created_at=datetime.now(
                timezone.utc
            ).isoformat(),
        )

    @property
    def manifest_hash(self) -> str:

        return _hash(
            asdict(self)
        )

    def save(
        self,
        path: str | Path,
    ) -> None:

        payload = asdict(self)

        payload[
            "manifest_hash"
        ] = self.manifest_hash

        Path(path).write_text(
            json.dumps(
                payload,
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )