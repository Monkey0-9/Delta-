from __future__ import annotations

from dataclasses import dataclass

from .schema import FinanceExample


@dataclass(frozen=True, slots=True)
class DatasetReport:
    total: int
    valid: int
    invalid: int
    duplicate_ids: int
    temporal_violations: int


class DatasetValidator:

    def validate(
        self,
        examples: list[FinanceExample],
    ) -> DatasetReport:

        seen: set[str] = set()

        invalid = 0
        duplicate_ids = 0
        temporal_violations = 0

        for example in examples:
            if example.example_id in seen:
                duplicate_ids += 1
                invalid += 1
                continue

            seen.add(example.example_id)

            try:
                example.validate_temporal_integrity()
            except ValueError:
                temporal_violations += 1
                invalid += 1

        return DatasetReport(
            total=len(examples),
            valid=len(examples) - invalid,
            invalid=invalid,
            duplicate_ids=duplicate_ids,
            temporal_violations=temporal_violations,
        )