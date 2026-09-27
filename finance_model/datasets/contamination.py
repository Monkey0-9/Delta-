from __future__ import annotations

from dataclasses import dataclass

from .schema import FinanceExample


@dataclass(frozen=True, slots=True)
class ContaminationReport:
    total: int
    contaminated: int
    duplicate_ids: int
    duplicate_sources: int

    @property
    def passed(self) -> bool:
        return (
            self.contaminated == 0
            and self.duplicate_ids == 0
            and self.duplicate_sources == 0
        )


class ContaminationDetector:

    def inspect(
        self,
        examples: list[FinanceExample],
    ) -> ContaminationReport:

        ids: set[str] = set()
        sources: set[str] = set()

        contaminated = 0
        duplicate_ids = 0
        duplicate_sources = 0

        for example in examples:

            if example.example_id in ids:
                duplicate_ids += 1

            ids.add(example.example_id)

            source_key = (
                example.source_hash
                if example.source_hash
                else example.example_id
            )

            if source_key in sources:
                duplicate_sources += 1

            sources.add(source_key)

            try:
                example.validate_temporal_integrity()
            except ValueError:
                contaminated += 1

        return ContaminationReport(
            total=len(examples),
            contaminated=contaminated,
            duplicate_ids=duplicate_ids,
            duplicate_sources=duplicate_sources,
        )