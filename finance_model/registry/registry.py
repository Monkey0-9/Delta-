from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from finance_model.architecture.model_spec import ModelSpec


class ModelRegistry:

    def __init__(
        self,
        root: str = "models/registry",
    ) -> None:
        self.root = Path(root)
        self.root.mkdir(
            parents=True,
            exist_ok=True,
        )

    def register(
        self,
        spec: ModelSpec,
    ) -> Path:

        path = self.root / (
            f"{spec.name}-{spec.version}.json"
        )

        if path.exists():
            raise FileExistsError(
                f"Model already registered: "
                f"{spec.identity()}"
            )

        payload = asdict(spec)

        payload["capabilities"] = [
            str(capability.value)
            for capability in spec.capabilities
        ]

        path.write_text(
            json.dumps(
                payload,
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )

        return path

    def get(
        self,
        name: str,
        version: str,
    ) -> dict:

        path = self.root / (
            f"{name}-{version}.json"
        )

        if not path.exists():
            raise KeyError(
                f"Model not registered: "
                f"{name}:{version}"
            )

        return json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )

    def exists(
        self,
        name: str,
        version: str,
    ) -> bool:

        return (
            self.root
            / f"{name}-{version}.json"
        ).exists()