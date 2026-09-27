from __future__ import annotations

import json
from pathlib import Path


class FINBenchRunner:

    def __init__(
        self,
        cases_path: Path,
    ):
        self.cases = json.loads(
            cases_path.read_text(
                encoding="utf-8"
            )
        )

    def dimensions(self):
        return sorted(
            {
                case["dimension"]
                for case in self.cases
            }
        )

    def summary(self):

        counts = {}

        for case in self.cases:
            dimension = case["dimension"]

            counts[dimension] = (
                counts.get(
                    dimension,
                    0,
                )
                + 1
            )

        return {
            "total_cases": len(self.cases),
            "dimensions": counts,
        }