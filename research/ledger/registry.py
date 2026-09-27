from __future__ import annotations

import json
from pathlib import Path
from threading import RLock
from typing import Any


class ResearchRegistry:
    """
    Append-oriented local research registry.

    A production implementation can later move the persistence
    layer to PostgreSQL/DuckDB/object storage without changing
    the experiment API.
    """

    def __init__(self, path: str | Path = "data/research/ledger.jsonl"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()

    def append(self, record: dict[str, Any]) -> None:
        payload = json.dumps(
            record,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )

        with self._lock:
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(payload)
                fh.write("\n")

    def list(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []

        with self._lock:
            rows = []

            with self.path.open("r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()

                    if not line:
                        continue

                    rows.append(json.loads(line))

            return rows

    def get(self, experiment_id: str) -> dict[str, Any] | None:
        for row in reversed(self.list()):
            # W45: support both flat (spec.to_dict) and nested (runner result) rows.
            if row.get("experiment_id") == experiment_id:
                return row
            nested = row.get("experiment")
            if isinstance(nested, dict) and nested.get("experiment_id") == experiment_id:
                return row

        return None