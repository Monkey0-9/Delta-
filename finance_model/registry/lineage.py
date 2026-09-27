from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ModelLineage:
    model_id: str
    base_model: str
    model_revision: str

    dataset_manifest_hash: str
    code_commit: str

    tokenizer_hash: str
    adapter_hash: str

    runtime_hash: str

    dtype: str
    quantization: str
    device: str

    training_config_hash: str

    lineage_hash: str = ""

    def finalized(self) -> "ModelLineage":
        payload = asdict(self)
        payload["lineage_hash"] = ""

        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")

        digest = hashlib.sha256(encoded).hexdigest()

        return ModelLineage(
            **{
                **payload,
                "lineage_hash": digest,
            }
        )


class LineageStore:

    def __init__(
        self,
        root: str = "models/lineage",
    ) -> None:
        self.root = Path(root)
        self.root.mkdir(
            parents=True,
            exist_ok=True,
        )

    def save(
        self,
        lineage: ModelLineage,
    ) -> Path:

        lineage = lineage.finalized()

        path = self.root / (
            f"{lineage.model_id}.json"
        )

        path.write_text(
            json.dumps(
                asdict(lineage),
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )

        return path

    def load(
        self,
        model_id: str,
    ) -> ModelLineage:

        path = self.root / f"{model_id}.json"

        if not path.exists():
            raise KeyError(
                f"Lineage not found: {model_id}"
            )

        data = json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )

        return ModelLineage(**data)